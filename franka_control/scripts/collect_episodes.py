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
from franka_control.data import CameraConfig, CollectionConfig, DataCollector
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
        "  Esc: end episode, then Y=success / N=failure"
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

    # Create collector
    collector = DataCollector(config, resume=args.resume)

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
            collector.start_episode(instruction=args.task_name)

            if args.device == "keyboard":
                logger.info("Recording... Controls:")
                for line in _keyboard_help().split("\n"):
                    logger.info(line)
            else:
                logger.info("Recording... Use SpaceMouse to control. Esc/Ctrl+C to end episode.")

            while running:
                loop_start = time.perf_counter()

                # Get observation and images
                obs = env.get_observation()

                images = {}
                if cameras is not None:
                    raw_images = cameras.read()
                    frame_ok = True
                    for cam in config.cameras:
                        cam_data = raw_images.get(cam.name, {})
                        if "rgb" not in cam_data:
                            logger.warning("Camera '%s' missing frame", cam.name)
                            frame_ok = False
                            break
                        images[cam.name] = cam_data["rgb"]

                    if not frame_ok:
                        collector.discard_episode()
                        break

                # Get teleop action
                raw_action, info = teleop.get_action()
                if info.get("exit_requested"):
                    success = _wait_success(teleop)
                    collector.end_episode(success=success)
                    break

                # Scale velocity to delta for delta modes
                if config.control_mode == "ee_delta":
                    raw_action[:6] *= dt
                elif config.control_mode == "joint_delta":
                    raw_action[:7] *= dt

                # Execute and record
                _, _, _, _, step_info = env.step(raw_action)
                applied_action = step_info["applied_action"]
                collector.record_frame(obs, applied_action, images)

                # Rate limiting
                elapsed = time.perf_counter() - loop_start
                if elapsed < dt:
                    time.sleep(dt - elapsed)

        logger.info("Collection complete. Finalizing dataset...")
        collector.finalize()

    finally:
        teleop.close()
        if cameras is not None:
            cameras.close()
        env.close()
        logger.info("Collection session ended.")


if __name__ == "__main__":
    main()
