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
from collections import deque

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

    step_count = 0

    # Latency instrumentation
    hist_action = deque()      # get_action() ms
    hist_step = deque()        # env.step() ms
    hist_loop = deque()        # full loop ms (incl sleep)
    hist_sleep = deque()       # sleep ms
    sec_action_max = 0.0
    sec_sleep_max = 0.0
    sec_t0 = 0.0

    def _print_sec(n_steps: int) -> None:
        """Print per-second summary."""
        if n_steps == 0:
            return
        steps_ms = [hist_step[i] for i in range(len(hist_step) - n_steps, len(hist_step))]
        p50 = sorted(steps_ms)[n_steps // 2]
        p95_idx = int(n_steps * 0.95)
        p95 = sorted(steps_ms)[min(p95_idx, n_steps - 1)]
        mx = max(steps_ms)
        logger.info(
            "  [1s] %d Hz | step p50=%.1f p95=%.1f max=%.1f ms | "
            "action_max=%.1f | sleep_max=%.1f ms",
            n_steps, p50, p95, mx, sec_action_max, sec_sleep_max,
        )

    def _print_final() -> None:
        """Print final distribution summary."""
        if not hist_step:
            return
        s = sorted(hist_step)
        n = len(s)
        logger.info(
            "Latency summary (n=%d): step min=%.1f p50=%.1f p95=%.1f max=%.1f ms",
            n, s[0], s[n // 2], s[int(n * 0.95)], s[-1],
        )
        if hist_action:
            a = sorted(hist_action)
            logger.info(
                "  action min=%.1f p50=%.1f max=%.1f ms",
                a[0], a[n // 2], a[-1],
            )

    try:
        logger.info("Connecting to robot...")
        obs, _ = env.reset()
        logger.info("Ready. Use SpaceMouse to control. Ctrl+C to stop.")

        dt = 1.0 / args.hz
        sec_t0 = time.perf_counter()
        sec_steps = 0

        while running:
            t0 = time.perf_counter()

            t1 = time.perf_counter()
            action, info = teleop.get_action()
            t_action = (time.perf_counter() - t1) * 1000
            hist_action.append(t_action)

            t2 = time.perf_counter()
            obs, reward, terminated, truncated, step_info = env.step(action)
            t_step = (time.perf_counter() - t2) * 1000
            hist_step.append(t_step)

            step_count += 1
            sec_steps += 1

            # Maintain frequency
            elapsed = time.perf_counter() - t0
            t_sleep = 0.0
            if elapsed < dt:
                time.sleep(dt - elapsed)
                t_sleep = (time.perf_counter() - t0 - elapsed) * 1000
            hist_sleep.append(t_sleep)

            t_loop = (time.perf_counter() - t0) * 1000
            hist_loop.append(t_loop)

            sec_action_max = max(sec_action_max, t_action)
            sec_sleep_max = max(sec_sleep_max, t_sleep)

            # Per-second summary
            if time.perf_counter() - sec_t0 >= 1.0:
                _print_sec(sec_steps)
                sec_steps = 0
                sec_action_max = 0.0
                sec_sleep_max = 0.0
                sec_t0 = time.perf_counter()

    finally:
        _print_final()
        teleop.close()
        env.close()
        logger.info("Teleop session ended (%d steps).", step_count)


if __name__ == "__main__":
    main()
