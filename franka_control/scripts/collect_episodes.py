"""Data collection script for teleoperation.

Usage:
    python -m franka_control.scripts.collect_episodes \\
        --robot-ip 192.168.0.100 \\
        --repo-id user/franka_pick \\
        --root data/franka_pick \\
        --device spacemouse \\
        --num-episodes 50
"""

import argparse
import logging
import signal
import time
from pathlib import Path

from franka_control.cameras import CameraManager
from franka_control.data import CameraConfig, CollectionConfig, DataCollector, StateStreamRecorder
from franka_control.envs import FrankaEnv
from franka_control.teleop import KeyboardTeleop, SpaceMouseTeleop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _keyboard_help() -> str:
    return (
        "  W/S: +/-X, A/D: +/-Y, R/F: +/-Z\n"
        "  Q/E: +/-Yaw, Z/X: +/-Pitch, C/V: +/-Roll\n"
        "  Space: close gripper, Enter: open gripper\n"
        "  Shift: slow mode (0.25x)\n"
        "  S: start recording, Esc: end episode"
    )


def _wait_success(teleop, timeout: float = 300.0) -> bool:
    """Wait for Y (success) or N (failure) key press via teleop.

    Returns True for success, False for failure.
    """
    logger.info("  Press Y=success / N=failure")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        action, info = teleop.get_action()
        pressed = info.get("pressed_keys", [])
        for key in pressed:
            if key in ("y",):
                return True
            if key in ("n",):
                return False
        time.sleep(0.01)
    logger.warning("Timeout waiting for success/failure, defaulting to failure")
    return False


def _read_cameras(cameras, config, last_images: dict) -> bool:
    """Read camera frames into last_images. Returns False on failure."""
    if cameras is None:
        return True
    raw_images = cameras.read()
    for cam in config.cameras:
        cam_data = raw_images.get(cam.name, {})
        if "rgb" not in cam_data:
            logger.warning("Camera '%s' missing frame", cam.name)
            return False
        last_images[cam.name] = cam_data["rgb"]
    return True


def main():
    parser = argparse.ArgumentParser(description="Collect robot demonstration data")

    # ── Dataset ──────────────────────────────────────────────────
    parser.add_argument("--robot-ip", required=True, help="Control machine IP")
    parser.add_argument("--repo-id", required=True, help="Dataset repo ID")
    parser.add_argument("--root", required=True, help="Local dataset directory")
    parser.add_argument("--task-name", default="manipulation", help="Task name / instruction")

    # ── Control ──────────────────────────────────────────────────
    parser.add_argument(
        "--control-mode",
        default="ee_delta",
        choices=["joint_abs", "joint_delta", "ee_abs", "ee_delta"],
        help="Robot control mode",
    )
    parser.add_argument("--fps", type=int, default=60, help="Recording frequency")
    parser.add_argument("--num-episodes", type=int, default=10, help="Number of episodes")
    parser.add_argument("--save-failure", action="store_true", help="Save failed episodes")

    # ── Teleop device ────────────────────────────────────────────
    parser.add_argument(
        "--device",
        default="spacemouse",
        choices=["spacemouse", "keyboard"],
        help="Teleop device",
    )
    parser.add_argument(
        "--action-scale-t",
        type=float,
        default=2.0,
        help="Translation max speed [m/s] (default: 2.0)",
    )
    parser.add_argument(
        "--action-scale-r",
        type=float,
        default=5.0,
        help="Rotation max speed [rad/s] (default: 5.0)",
    )
    parser.add_argument(
        "--freeze-rotation",
        action="store_true",
        help="Ignore rotation input (3-DOF translation only)",
    )
    parser.add_argument(
        "--gripper-mode",
        default="binary",
        choices=["binary", "continuous", "none"],
        help="Gripper control mode (default: binary)",
    )

    # ── SpaceMouse-specific ──────────────────────────────────────
    parser.add_argument(
        "--deadzone",
        type=float,
        default=0.001,
        help="SpaceMouse deadzone (default: 0.001)",
    )

    # ── Camera ───────────────────────────────────────────────────
    parser.add_argument("--no-camera", action="store_true", help="Disable cameras")
    parser.add_argument(
        "--camera-serials",
        nargs="+",
        default=["xxx", "yyy"],
        help="Camera serial numbers (space-separated)",
    )
    parser.add_argument(
        "--camera-names",
        nargs="+",
        default=["wrist", "third_person"],
        help="Camera names (space-separated, must match --camera-serials length)",
    )

    # ── Other ────────────────────────────────────────────────────
    parser.add_argument("--resume", action="store_true", help="Resume existing dataset")

    args = parser.parse_args()

    # Validate camera config
    if not args.no_camera and len(args.camera_serials) != len(args.camera_names):
        parser.error("--camera-serials and --camera-names must have same length")

    # Configuration
    cameras_list = [] if args.no_camera else [
        CameraConfig(
            name=name, serial=serial, width=640, height=480, fps=60
        )
        for name, serial in zip(args.camera_names, args.camera_serials)
    ]

    gripper_mode = None if args.gripper_mode == "none" else args.gripper_mode

    config = CollectionConfig(
        repo_id=args.repo_id,
        root=Path(args.root),
        task_name=args.task_name,
        robot_ip=args.robot_ip,
        gripper_host=args.robot_ip,
        control_mode=args.control_mode,
        gripper_mode=gripper_mode or "binary",
        fps=args.fps,
        cameras=cameras_list,
        save_failure=args.save_failure,
    )

    # Create hardware interfaces
    env = FrankaEnv(
        robot_ip=config.robot_ip,
        action_mode=config.control_mode,
        gripper_host=config.gripper_host,
        gripper_port=config.gripper_port,
        gripper_mode=config.gripper_mode,
    )

    # Cameras
    if config.cameras:
        camera_config = {
            cam.name: {
                "serial": cam.serial,
                "resolution": (cam.width, cam.height),
                "fps": cam.fps,
            }
            for cam in config.cameras
        }
        cameras = CameraManager(camera_config)
    else:
        cameras = None
        logger.info("Cameras disabled (--no-camera)")

    # Teleop
    action_scale = (args.action_scale_t, args.action_scale_r)
    teleop_cls = SpaceMouseTeleop if args.device == "spacemouse" else KeyboardTeleop

    teleop_kwargs = {
        "action_scale": action_scale,
        "freeze_rotation": args.freeze_rotation,
        "gripper_mode": gripper_mode,
    }
    if args.device == "spacemouse":
        teleop_kwargs["deadzone"] = args.deadzone

    teleop = teleop_cls(**teleop_kwargs)

    # Create collector and state recorder
    collector = DataCollector(config, resume=args.resume)
    recorder = StateStreamRecorder(lambda: env._robot, fps=config.fps)

    # Log configuration
    logger.info(
        "Config: mode=%s, device=%s, fps=%d, gripper=%s, cameras=%s, "
        "action_scale=(%.1f, %.1f), freeze_rotation=%s",
        args.control_mode, args.device, args.fps, args.gripper_mode,
        "off" if cameras is None else f"{len(config.cameras)}x",
        action_scale[0], action_scale[1], args.freeze_rotation,
    )

    # Graceful shutdown
    running = True

    def _signal_handler(sig, frame):
        nonlocal running
        running = False
        logger.info("Shutting down...")

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        logger.info("Resetting to home position...")
        env.reset()

        dt = 1.0 / config.fps

        for ep_idx in range(args.num_episodes):
            if not running:
                break

            logger.info("=" * 50)
            logger.info("Episode %d/%d — instruction: %s", ep_idx + 1, args.num_episodes, args.task_name)

            env.reset()
            recording = False
            record_start_time = 0.0
            record_count = 0
            sec_frames = 0
            sec_t0 = time.perf_counter()
            last_images = {}
            last_applied_action = None

            if args.device == "keyboard":
                logger.info("Preview mode — move robot to start position. Controls:")
                for line in _keyboard_help().split("\n"):
                    logger.info(line)
            else:
                logger.info("Preview mode — move robot to start position.")
                logger.info("  SpaceMouse left button = start recording, Esc = skip episode.")

            # ── Phase 1: Preview (move without recording) ──────────
            while running:
                loop_start = time.perf_counter()
                raw_action, info = teleop.get_action()

                if info.get("exit_requested"):
                    if recording:
                        _end_recording(recorder, collector, last_applied_action,
                                       last_images, record_count, record_start_time, teleop)
                    else:
                        logger.info("Episode skipped.")
                    break

                # Check for start trigger: keyboard 's' or spacemouse left button
                if not recording:
                    pressed = info.get("pressed_keys", [])
                    buttons = info.get("buttons", [0, 0])
                    if "s" in pressed or buttons[0]:
                        recording = True
                        record_start_time = time.perf_counter()
                        record_count = 0
                        sec_frames = 0
                        sec_t0 = time.perf_counter()
                        # Start background state recorder
                        init_obs = env.get_observation()
                        recorder.gripper_width = init_obs["gripper_width"][0]
                        recorder.start()
                        collector.start_episode(instruction=args.task_name)
                        logger.info(">>> Recording started <<<")
                        teleop.clear_pressed_keys()

                if not recording:
                    # Preview: execute action but don't record
                    if config.control_mode == "ee_delta":
                        raw_action[:6] *= dt
                    elif config.control_mode == "joint_delta":
                        raw_action[:7] *= dt
                    env.step(raw_action)
                    elapsed = time.perf_counter() - loop_start
                    if elapsed < dt:
                        time.sleep(dt - elapsed)
                    continue

                # ── Phase 2: Recording (dual-thread) ───────────────
                if not _read_cameras(cameras, config, last_images):
                    recorder.stop()
                    collector.discard_episode()
                    break

                # Scale velocity to delta for delta modes
                if config.control_mode == "ee_delta":
                    raw_action[:6] *= dt
                elif config.control_mode == "joint_delta":
                    raw_action[:7] *= dt

                # Execute action (may block on gripper)
                obs_after, _, _, _, step_info = env.step(raw_action)
                applied_action = step_info["applied_action"]
                recorder.gripper_width = obs_after["gripper_width"][0]
                last_applied_action = applied_action

                # Drain accumulated frames from background thread
                drained = recorder.drain()
                for frame_obs in drained:
                    collector.record_frame(frame_obs, applied_action, last_images)
                    record_count += 1
                    sec_frames += 1

                # If no frames accumulated (fast step), record one from result
                if not drained:
                    collector.record_frame(obs_after, applied_action, last_images)
                    record_count += 1
                    sec_frames += 1

                # Per-second FPS report
                now = time.perf_counter()
                if now - sec_t0 >= 1.0:
                    logger.info(
                        "[1s] %d fps | total frames=%d",
                        sec_frames, record_count,
                    )
                    sec_frames = 0
                    sec_t0 = now

                # Rate limiting
                elapsed = time.perf_counter() - loop_start
                if elapsed < dt:
                    time.sleep(dt - elapsed)

            # Stop recorder after episode ends
            recorder.stop()

        logger.info("Collection complete. Finalizing dataset...")
        collector.finalize()

    finally:
        teleop.close()
        if cameras is not None:
            cameras.close()
        env.close()
        logger.info("Collection session ended.")


def _end_recording(recorder, collector, last_applied_action, last_images,
                   record_count, record_start_time, teleop) -> int:
    """Stop recorder, drain remaining frames, end episode.

    Returns total frame count including drained frames.
    """
    recorder.stop()
    extra = 0
    if last_applied_action is not None:
        for frame_obs in recorder.drain():
            collector.record_frame(frame_obs, last_applied_action, last_images)
            extra += 1
    total = record_count + extra
    duration = time.perf_counter() - record_start_time
    avg_fps = total / max(duration, 0.001)
    logger.info(
        "Episode stats: %d frames, %.1fs, avg %.1f fps",
        total, duration, avg_fps,
    )
    success = _wait_success(teleop)
    collector.end_episode(success=success)
    return total


if __name__ == "__main__":
    main()

