"""Teleoperation main loop.

Usage:
    python -m franka_control.scripts.teleop --robot-ip 192.168.0.2

Controls:
    SpaceMouse: 6-DOF Cartesian delta control
    Left button: close gripper
    Right button: open gripper
    Ctrl+C: stop
"""

import argparse
import logging
import signal
import time

from franka_control.envs.franka_env import FrankaEnv
from franka_control.teleop.spacemouse_teleop import SpaceMouseTeleop

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Franka SpaceMouse Teleop")
    parser.add_argument("--robot-ip", required=True, help="Control machine IP")
    parser.add_argument("--gripper-host", default=None,
                        help="Gripper server host (default: same as --robot-ip)")
    parser.add_argument("--gripper-port", type=int, default=5556)
    parser.add_argument(
        "--action-scale-t", type=float, default=0.04,
        help="Translation action scale [m] (default: 0.04)",
    )
    parser.add_argument(
        "--action-scale-r", type=float, default=0.2,
        help="Rotation action scale [rad] (default: 0.2)",
    )
    parser.add_argument(
        "--hz", type=int, default=10, help="Control frequency [Hz] (default: 10)"
    )
    args = parser.parse_args()

    # Default gripper_host to robot_ip
    if args.gripper_host is None:
        args.gripper_host = args.robot_ip

    # Graceful shutdown
    running = True

    def _signal_handler(sig, frame):
        nonlocal running
        running = False
        logger.info("Shutting down...")

    signal.signal(signal.SIGINT, _signal_handler)

    # Create env + teleop
    use_gripper = args.gripper_host is not None
    env = FrankaEnv(
        robot_ip=args.robot_ip,
        gripper_host=args.gripper_host,
        gripper_port=args.gripper_port,
        action_mode="ee_delta",
        gripper_mode="binary" if use_gripper else "continuous",
    )

    teleop = SpaceMouseTeleop(
        action_scale=(args.action_scale_t, args.action_scale_r),
        gripper_mode="binary" if use_gripper else None,
    )

    try:
        logger.info("Connecting to robot...")
        obs, _ = env.reset()
        logger.info("Ready. Use SpaceMouse to control. Ctrl+C to stop.")

        dt = 1.0 / args.hz
        step_count = 0

        while running:
            t_start = time.time()

            action, info = teleop.get_action()

            obs, reward, terminated, truncated, step_info = env.step(action)
            step_count += 1

            if step_count % args.hz == 0:
                logger.info(
                    "Step %d | intervened=%s | buttons=%s | ee_pos=[%.3f, %.3f, %.3f]",
                    step_count,
                    info["intervened"],
                    info["buttons"],
                    obs["ee_pos"][0], obs["ee_pos"][1], obs["ee_pos"][2],
                )

            # Maintain frequency
            elapsed = time.time() - t_start
            if elapsed < dt:
                time.sleep(dt - elapsed)

    finally:
        teleop.close()
        env.close()
        logger.info("Teleop session ended (%d steps).", step_count)


if __name__ == "__main__":
    main()
