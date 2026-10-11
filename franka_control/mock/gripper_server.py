"""Mock GripperServer: the real protocol on a simulated Franka Hand.

``SimHand`` mirrors pylibfranka.Gripper's blocking behavior — a stroke takes
``distance / speed`` seconds (the real hand travels at up to 0.1 m/s, so a
full close is ~0.8 s) — which keeps the "blocking grasp()" timing that the
data collection pipeline and the deploy loop must tolerate.

Usage:
    python -m franka_control.mock.gripper_server [--port 5556] [--object-width 0.03]
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from types import SimpleNamespace
from typing import Optional

from franka_control.gripper.gripper_server import (
    DEFAULT_CMD_PORT,
    DEFAULT_STATE_POLL_HZ,
    GripperServer,
)

logger = logging.getLogger(__name__)

MAX_WIDTH = 0.08


class SimHand:
    """pylibfranka.Gripper-shaped simulated Franka Hand.

    Args:
        object_width: If set, closing below this finger width stops there and
            reports ``is_grasped``; ``grasp()`` then returns False, like the
            real hand when an object blocks the target width.
    """

    def __init__(self, object_width: Optional[float] = None):
        self._object_width = object_width
        self._lock = threading.Lock()
        self._abort = threading.Event()
        self._width = 0.04
        self._is_grasped = False

    # ── pylibfranka.Gripper API ──────────────────────────────────

    def homing(self) -> bool:
        """Calibration: open fully (takes ~0.5 s at the default speed)."""
        self._travel_to(MAX_WIDTH, 0.08)
        self._set(grasped=False)
        return True

    def move(self, width: float, speed: float) -> bool:
        self._travel_to(self._clip(width), speed)
        self._set(grasped=False)
        return True

    def grasp(self, width, speed, force, epsilon_inner=0.005, epsilon_outer=0.005) -> bool:
        target = self._clip(width)
        with self._lock:
            start = self._width
        blocked = self._object_width is not None and target < self._object_width <= start
        self._travel_to(self._object_width if blocked else target, speed)
        self._set(grasped=blocked)
        return not blocked

    def stop(self) -> bool:
        """Unblock an in-flight motion (the real gripper stops physically)."""
        self._abort.set()
        return True

    def read_once(self):
        with self._lock:
            return SimpleNamespace(
                width=self._width,
                max_width=MAX_WIDTH,
                is_grasped=self._is_grasped,
                temperature=30,
            )

    # ── Internals ────────────────────────────────────────────────

    @staticmethod
    def _clip(width: float) -> float:
        return min(max(float(width), 0.0), MAX_WIDTH)

    def _set(self, grasped: bool) -> None:
        with self._lock:
            self._is_grasped = grasped

    def _travel_to(self, width: float, speed: float) -> None:
        """Move the fingers over ``distance / speed`` seconds, abortable.

        The width advances continuously (like real fingers), so readers of
        ``read_once()`` see mid-stroke positions instead of a jump.
        """
        self._abort.clear()
        with self._lock:
            start = self._width
        duration = abs(width - start) / max(float(speed), 1e-6)
        t0 = time.monotonic()
        deadline = t0 + duration
        while True:
            now = time.monotonic()
            fraction = 1.0 if duration <= 0 else min(1.0, max(0.0, (now - t0) / duration))
            with self._lock:
                self._width = start + (width - start) * fraction
            if now >= deadline or self._abort.is_set():
                break
            time.sleep(min(0.005, deadline - now))


class MockGripperServer(GripperServer):
    """GripperServer whose hardware is a SimHand (no gripper required)."""

    def __init__(self, *args, object_width: Optional[float] = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.object_width = object_width

    def _create_gripper(self) -> SimHand:
        logger.info("Simulated Franka Hand ready (no hardware).")
        return SimHand(object_width=self.object_width)


def main():
    parser = argparse.ArgumentParser(
        description="Mock Franka Gripper ZMQ Server (simulated hand, no hardware)"
    )
    parser.add_argument("--robot-ip", default="sim",
                        help="Unused (kept for CLI parity with the real server)")
    parser.add_argument("--port", type=int, default=DEFAULT_CMD_PORT,
                        help=f"ZMQ port (default: {DEFAULT_CMD_PORT})")
    parser.add_argument("--poll-hz", type=float, default=DEFAULT_STATE_POLL_HZ,
                        help=f"State poll Hz (default: {DEFAULT_STATE_POLL_HZ})")
    parser.add_argument("--object-width", type=float, default=None,
                        help="Simulate an object this wide [m]; grasp() then "
                             "stops there and returns False (default: none)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    server = MockGripperServer(
        args.robot_ip,
        cmd_port=args.port,
        state_poll_hz=args.poll_hz,
        object_width=args.object_width,
    )

    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down ...", sig)
        server._running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    server.start()
    server.run()


if __name__ == "__main__":
    main()
