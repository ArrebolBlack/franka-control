"""Data collection script for Franka robot.

Usage:
    python -m franka_control.scripts.collect_data \
        --robot-ip 172.16.0.2 \
        --gripper-host 172.16.0.2 \
        --cameras '{"front": "138422075015"}' \
        --repo-id franka_pick_place \
        --fps 30

Controls (raw terminal mode):
    r: Start new episode
    s: Stop current episode early
    y: Mark episode as successful
    n: Mark episode as failed
    d: Discard current episode
    Ctrl+C: Exit and finalize dataset
"""

from __future__ import annotations

import argparse
import json
import logging
import select
import sys
import termios
import time
import tty

from franka_control.cameras import CameraManager
from franka_control.data.collector import DataCollector
from franka_control.envs.franka_env import FrankaEnv
from franka_control.teleop import SpaceMouseTeleop

logger = logging.getLogger(__name__)


def _check_key() -> str | None:
    """Non-blocking key read in raw terminal mode."""
    if select.select([sys.stdin], [], [], 0)[0]:
        ch = sys.stdin.read(1)
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch
    return None


def main():
    parser = argparse.ArgumentParser(description="Franka Data Collection")
    parser.add_argument("--robot-ip", required=True)
    parser.add_argument("--gripper-host", default=None)
    parser.add_argument("--gripper-port", type=int, default=5556)
    parser.add_argument(
        "--cameras", default=None,
        help='JSON: {"name": "serial", ...}',
    )
    parser.add_argument("--repo-id", required=True, help="Dataset name")
    parser.add_argument("--root", default=None, help="Dataset directory")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument(
        "--num-episodes", type=int, default=0,
        help="Max episodes (0=unlimited)",
    )
    parser.add_argument("--task", default="", help="Task description")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    # Default gripper_host to robot_ip
    if args.gripper_host is None:
        args.gripper_host = args.robot_ip

    # Camera config
    cam_config = None
    cam_names = None
    if args.cameras:
        cam_serials = json.loads(args.cameras)
        cam_names = list(cam_serials.keys())
        cam_config = {
            name: {
                "serial": serial,
                "resolution": (640, 480),
                "fps": 60,
                "depth": False,
            }
            for name, serial in cam_serials.items()
        }

    # Create components
    use_gripper = args.gripper_host is not None
    env = FrankaEnv(
        robot_ip=args.robot_ip,
        gripper_host=args.gripper_host,
        gripper_port=args.gripper_port,
        action_mode="ee_delta",
        gripper_mode="binary" if use_gripper else "continuous",
    )
    teleop = SpaceMouseTeleop(
        action_scale=(0.04, 0.2),
        gripper_mode="binary" if use_gripper else None,
    )
    camera_mgr = CameraManager(cam_config) if cam_config else None

    collector = DataCollector(
        repo_id=args.repo_id,
        fps=args.fps,
        root=args.root,
        cameras=cam_names,
        resume=args.resume,
    )

    # Raw terminal for key input
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())

    try:
        logger.info("Connecting to robot...")
        obs, _ = env.reset()
        logger.info("Ready. r=start, s=stop, Ctrl+C=exit")

        dt = 1.0 / args.fps
        episode_count = 0

        while args.num_episodes == 0 or episode_count < args.num_episodes:
            # Wait for 'r' to start
            logger.info("[Episode %d] Press 'r' to start", episode_count + 1)
            while True:
                ch = _check_key()
                if ch == "r":
                    break
                time.sleep(0.01)

            # Reset and start recording
            obs, _ = env.reset()
            logger.info("[Episode %d] Recording... 's'=stop", episode_count + 1)

            step = 0
            while step < args.max_steps:
                t_start = time.time()

                action, info = teleop.get_action()
                obs, _, _, _, _ = env.step(action)
                images = camera_mgr.read() if camera_mgr else None

                collector.add_frame(obs, action, images, task=args.task)
                step += 1

                if step % 30 == 0:
                    logger.info("  Step %d/%d", step, args.max_steps)

                if _check_key() == "s":
                    logger.info("Stopped by user at step %d", step)
                    break

                elapsed = time.time() - t_start
                if elapsed < dt:
                    time.sleep(dt - elapsed)

            # Ask outcome
            logger.info("y=success / n=fail / d=discard")
            while True:
                ch = _check_key()
                if ch == "y":
                    collector.save_episode(success=True)
                    episode_count += 1
                    logger.info("Episode %d saved (success)", episode_count)
                    break
                elif ch == "n":
                    collector.save_episode(success=False)
                    episode_count += 1
                    logger.info("Episode %d saved (failed)", episode_count)
                    break
                elif ch == "d":
                    collector.discard_episode()
                    logger.info("Episode discarded")
                    break
                time.sleep(0.01)

    except KeyboardInterrupt:
        logger.info("Interrupted.")

    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        collector.finalize()
        teleop.close()
        if camera_mgr:
            camera_mgr.close()
        env.close()
        logger.info("Done. %d episodes saved.", collector.num_episodes)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    main()
