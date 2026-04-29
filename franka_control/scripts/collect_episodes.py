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
import os
import select
import signal
import sys
import termios
import time
from pathlib import Path
import tty

import numpy as np

# Import OpenCV before LeRobot/data modules. In the franka environment,
# importing cv2 after lerobot can make Qt HighGUI hang inside imshow().
try:
    import cv2 as _cv2
except ImportError as _cv2_import_error:
    _cv2 = None
else:
    _cv2_import_error = None

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


def _spacemouse_help() -> str:
    return (
        "  SpaceMouse: 6-DOF movement\n"
        "  Left button: close gripper, Right button: open gripper\n"
        "  Keyboard: s=start, e=end, f=discard, q=quit"
    )


def _set_cbreak(fd: int) -> list:
    """Switch terminal to cbreak mode for single-key commands."""
    return tty.setcbreak(fd)


def _set_normal(fd: int, old_settings: list) -> None:
    """Restore terminal settings."""
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _read_key(fd: int, timeout: float = 0.0) -> str | None:
    """Read one key from raw stdin without blocking the control loop."""
    ready, _, _ = select.select([fd], [], [], timeout)
    if not ready:
        return None
    return os.read(fd, 1).decode("utf-8", errors="ignore")


class Display:
    """Optional OpenCV display with reliable event polling."""

    def __init__(self, mode: str = "auto", window_name: str = "Data Collection"):
        self.mode = mode
        self.window_name = window_name
        self.enabled = False
        self._cv2 = None
        self._pending_key: str | None = None

        if mode == "off":
            logger.info("Display disabled (--display off)")
            return

        if _cv2 is None:
            self._handle_unavailable("OpenCV is not installed", _cv2_import_error)
            return

        cv2 = _cv2
        reason = self._unavailable_reason(cv2)
        if reason:
            self._handle_unavailable(reason)
            return

        self._cv2 = cv2
        self.enabled = True
        logger.info("OpenCV display enabled")

    def _handle_unavailable(self, reason: str, exc: Exception | None = None) -> None:
        if self.mode == "on":
            raise RuntimeError(f"Display requested but unavailable: {reason}") from exc
        logger.warning("Display disabled: %s", reason)

    def _unavailable_reason(self, cv2) -> str | None:
        if sys.platform.startswith("linux") and not (
            os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY")
        ):
            return "DISPLAY/WAYLAND_DISPLAY is not set"

        try:
            build_info = cv2.getBuildInformation()
        except Exception:
            return None

        for line in build_info.splitlines():
            stripped = line.strip()
            if stripped.startswith("GUI:"):
                gui_backend = stripped.split(":", 1)[1].strip().upper()
                if gui_backend in ("", "NONE", "NO"):
                    return "OpenCV was built without HighGUI support"
                return None
        return None

    def read_key(self, delay_ms: int = 1) -> str | None:
        """Read a key from the OpenCV window event queue."""
        if not self.enabled or self._cv2 is None:
            return None
        if self._pending_key is not None:
            key = self._pending_key
            self._pending_key = None
            return key
        return self._poll_key(delay_ms)

    def show(
        self,
        images: dict[str, np.ndarray],
        state: str,
        fps: float = 0,
        frame_count: int = 0,
    ) -> None:
        """Show concatenated camera feeds and pump the OpenCV event loop."""
        if not self.enabled or self._cv2 is None or not images:
            return

        cv2 = self._cv2
        frames = []
        for rgb in images.values():
            frame = rgb
            if frame.ndim == 3 and frame.shape[2] == 3:
                frame = np.ascontiguousarray(frame[:, :, ::-1])
            else:
                frame = np.ascontiguousarray(frame)
            frames.append(frame)

        h = frames[0].shape[0]
        resized = []
        for frame in frames:
            if frame.shape[0] != h:
                w = int(frame.shape[1] * h / frame.shape[0])
                frame = cv2.resize(frame, (w, h))
            resized.append(frame)
        display = np.hstack(resized)

        color = (0, 255, 0) if state == "RECORDING" else (0, 200, 255)
        cv2.putText(
            display, state, (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2,
        )

        parts = []
        if fps > 0:
            parts.append(f"FPS: {int(fps)}")
        if frame_count > 0:
            parts.append(f"Frames: {frame_count}")
        if parts:
            cv2.putText(
                display, " | ".join(parts), (10, 60),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1,
            )

        cv2.imshow(self.window_name, display)
        key = self._poll_key(delay_ms=1)
        if key is not None and self._pending_key is None:
            self._pending_key = key

    def close(self) -> None:
        if self.enabled and self._cv2 is not None:
            self._cv2.destroyAllWindows()

    def _poll_key(self, delay_ms: int = 1) -> str | None:
        key = self._cv2.waitKey(delay_ms)
        if key < 0:
            return None
        key &= 0xFF
        if key == 255:
            return None
        return chr(key)


def _read_command_key(raw_fd: int | None, display: Display | None) -> str | None:
    """Read one episode-control key from terminal or OpenCV window."""
    key = _read_key(raw_fd, timeout=0.0) if raw_fd is not None else None
    if key is not None:
        return key
    if display is not None:
        return display.read_key(delay_ms=1)
    return None


def _wait_success(
    teleop,
    timeout: float = 300.0,
    raw_fd: int | None = None,
    display: Display | None = None,
) -> bool:
    """Wait for Y (success) or N (failure) key press via teleop."""
    logger.info("  Press Y=success / N=failure")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        key = _read_key(raw_fd, timeout=0.05) if raw_fd is not None else None
        if key is None and display is not None:
            key = display.read_key(delay_ms=1)
        if key in ("y", "Y"):
            return True
        if key in ("n", "N"):
            return False

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
    parser.add_argument(
        "--gripper-host",
        default=None,
        help="Gripper server host (default: same as --robot-ip)",
    )
    parser.add_argument("--gripper-port", type=int, default=5556)
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
        "--cameras",
        default="config/cameras.yaml",
        help="Camera config YAML path (default: config/cameras.yaml)",
    )
    parser.add_argument(
        "--display",
        default="auto",
        choices=["auto", "on", "off"],
        help="Camera preview display mode (default: auto)",
    )

    # ── Other ────────────────────────────────────────────────────
    parser.add_argument("--resume", action="store_true", help="Resume existing dataset")

    args = parser.parse_args()

    # Camera setup
    if args.no_camera:
        cameras = None
        cameras_list = []
    else:
        cameras = CameraManager.from_yaml(args.cameras)
        cameras_list = [
            CameraConfig(
                name=name,
                serial=cam._serial,
                width=cam._resolution[0],
                height=cam._resolution[1],
                fps=cam._fps,
            )
            for name, cam in cameras._cameras.items()
        ]

    gripper_mode = None if args.gripper_mode == "none" else args.gripper_mode

    config = CollectionConfig(
        repo_id=args.repo_id,
        root=Path(args.root),
        task_name=args.task_name,
        robot_ip=args.robot_ip,
        gripper_host=args.gripper_host or args.robot_ip,
        gripper_port=args.gripper_port,
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

    if cameras is not None:
        logger.info("Cameras: %s", cameras.camera_names)
    else:
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
    recorder = StateStreamRecorder(lambda: env._robot, cameras=cameras, fps=config.fps)
    display = Display(args.display)

    raw_fd = None
    old_term = None

    logger.info(
        "Config: mode=%s, device=%s, fps=%d, gripper=%s, cameras=%s, display=%s, "
        "action_scale=(%.1f, %.1f), freeze_rotation=%s",
        args.control_mode, args.device, args.fps, args.gripper_mode,
        "off" if cameras is None else f"{len(config.cameras)}x", args.display,
        action_scale[0], action_scale[1], args.freeze_rotation,
    )

    running = True

    def _signal_handler(sig, frame):
        nonlocal running
        running = False
        logger.info("Shutting down...")

    signal.signal(signal.SIGINT, _signal_handler)

    try:
        if args.device == "spacemouse":
            if sys.stdin.isatty():
                raw_fd = sys.stdin.fileno()
                old_term = _set_cbreak(raw_fd)
            else:
                logger.warning(
                    "stdin is not a TTY; keyboard episode commands are unavailable"
                )

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
                for line in _spacemouse_help().split("\n"):
                    logger.info(line)

            # ── Phase 1: Preview (move without recording) ──────────
            while running:
                loop_start = time.perf_counter()
                raw_action, info = teleop.get_action()
                command_key = (
                    _read_command_key(raw_fd, display)
                    if args.device == "spacemouse"
                    else None
                )

                if args.device == "spacemouse" and command_key:
                    if command_key in ("q", "\x03"):
                        if recording:
                            recorder.stop()
                            collector.discard_episode()
                            logger.info("Active episode discarded before quit.")
                        running = False
                        break
                    if command_key == "f":
                        if recording:
                            recorder.stop()
                            collector.discard_episode()
                            logger.info("Episode discarded.")
                        else:
                            logger.info("Episode skipped.")
                        break
                    if command_key == "e" and recording:
                        _end_recording(
                            recorder, collector, last_applied_action,
                            last_images, record_count, record_start_time,
                            teleop, raw_fd=raw_fd, display=display,
                        )
                        break

                if info.get("exit_requested"):
                    if recording:
                        _end_recording(recorder, collector, last_applied_action,
                                       last_images, record_count, record_start_time,
                                       teleop, display=display)
                    else:
                        logger.info("Episode skipped.")
                    break

                if not recording:
                    if args.device == "spacemouse":
                        start_requested = command_key == "s"
                    else:
                        pressed = info.get("pressed_keys", [])
                        start_requested = "s" in pressed

                    if start_requested:
                        recording = True
                        record_start_time = time.perf_counter()
                        record_count = 0
                        sec_frames = 0
                        sec_t0 = time.perf_counter()
                        _read_cameras(cameras, config, last_images)
                        init_obs = env.get_observation()
                        recorder.gripper_width = init_obs["gripper_width"][0]
                        recorder.start()
                        collector.start_episode(instruction=args.task_name)
                        logger.info(">>> Recording started <<<")
                        if hasattr(teleop, "clear_pressed_keys"):
                            teleop.clear_pressed_keys()

                if not recording:
                    if config.control_mode == "ee_delta":
                        raw_action[:6] *= dt
                    elif config.control_mode == "joint_delta":
                        raw_action[:7] *= dt
                    env.step(raw_action)
                    _read_cameras(cameras, config, last_images)
                    if args.device == "spacemouse":
                        overlay = "PREVIEW - Press S=start E=end F=discard Q=quit"
                    else:
                        overlay = "PREVIEW - Press S to start"
                    display.show(last_images, overlay)
                    elapsed = time.perf_counter() - loop_start
                    if elapsed < dt:
                        time.sleep(dt - elapsed)
                    continue

                # ── Phase 2: Recording (dual-thread) ───────────────
                # Cameras are read by recorder background thread

                if config.control_mode == "ee_delta":
                    raw_action[:6] *= dt
                elif config.control_mode == "joint_delta":
                    raw_action[:7] *= dt

                # Execute action (may block on gripper)
                obs_after, _, _, _, step_info = env.step(raw_action)
                applied_action = step_info["applied_action"]
                recorder.gripper_width = obs_after["gripper_width"][0]
                last_applied_action = applied_action

                # Drain accumulated (obs, images) from background thread
                drained = recorder.drain()
                for frame_obs, _, frame_images in drained:
                    images_to_use = frame_images if frame_images else last_images
                    collector.record_frame(frame_obs, applied_action, images_to_use)
                    if images_to_use:
                        last_images = images_to_use
                    record_count += 1
                    sec_frames += 1

                # If no frames accumulated, record one from step result
                if not drained:
                    images_to_use = recorder.last_images or last_images
                    collector.record_frame(obs_after, applied_action, images_to_use)
                    if images_to_use:
                        last_images = images_to_use
                    record_count += 1
                    sec_frames += 1

                # Show camera display (main thread — freezes during gripper blocking)
                window_elapsed = time.perf_counter() - sec_t0
                current_fps = sec_frames / max(window_elapsed, 1e-3)
                if args.device == "spacemouse":
                    rec_overlay = "REC - E=end F=discard Q=quit"
                else:
                    rec_overlay = "REC - Esc=end"
                display.show(
                    recorder.last_images or last_images,
                    rec_overlay,
                    fps=current_fps,
                    frame_count=record_count,
                )

                # Per-second FPS report
                now = time.perf_counter()
                window_elapsed = now - sec_t0
                if window_elapsed >= 1.0:
                    window_fps = sec_frames / window_elapsed
                    logger.info(
                        "[1s] %.1f fps | total frames=%d",
                        window_fps, record_count,
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
        if old_term is not None and raw_fd is not None:
            _set_normal(raw_fd, old_term)
        teleop.close()
        if cameras is not None:
            cameras.close()
        env.close()
        display.close()
        logger.info("Collection session ended.")


def _end_recording(recorder, collector, last_applied_action, last_images,
                   record_count, record_start_time, teleop,
                   raw_fd: int | None = None,
                   display: Display | None = None) -> int:
    """Stop recorder, drain remaining frames, end episode."""
    recorder.stop()
    extra = 0
    if last_applied_action is not None:
        for frame_obs, _, frame_images in recorder.drain():
            images_to_use = frame_images if frame_images else last_images
            collector.record_frame(frame_obs, last_applied_action, images_to_use)
            extra += 1
    total = record_count + extra
    duration = time.perf_counter() - record_start_time
    avg_fps = total / max(duration, 0.001)
    logger.info(
        "Episode stats: %d frames, %.1fs, avg %.1f fps",
        total, duration, avg_fps,
    )
    success = _wait_success(teleop, raw_fd=raw_fd, display=display)
    collector.end_episode(success=success)
    return total


if __name__ == "__main__":
    main()
