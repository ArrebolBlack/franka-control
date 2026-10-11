"""Run the mock robot + gripper servers in one process.

Stage-1 convenience: one terminal instead of two, with ports checked up
front so a real server on the same machine fails loudly instead of silently.

Usage:
    python -m franka_control.mock.launch [--viewer] [--object-width 0.03]
"""

from __future__ import annotations

import argparse
import logging
import signal
import socket
import threading

from franka_control.gripper.gripper_server import DEFAULT_CMD_PORT as DEFAULT_GRIPPER_PORT
from franka_control.mock.gripper_server import MockGripperServer
from franka_control.mock.robot_server import MockRobotServer
from franka_control.robot.robot_server import (
    DEFAULT_CMD_PORT as DEFAULT_ROBOT_PORT,
    DEFAULT_STATE_POLL_HZ,
    DEFAULT_STATE_STREAM_PORT,
)

logger = logging.getLogger(__name__)


def _port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("", port))
        except OSError:
            return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Launch the mock robot + gripper servers")
    parser.add_argument("--robot-port", type=int, default=DEFAULT_ROBOT_PORT)
    parser.add_argument("--state-stream-port", type=int, default=DEFAULT_STATE_STREAM_PORT)
    parser.add_argument("--gripper-port", type=int, default=DEFAULT_GRIPPER_PORT)
    parser.add_argument("--poll-hz", type=float, default=DEFAULT_STATE_POLL_HZ)
    parser.add_argument("--sim-set-hz", type=float, default=50.0)
    parser.add_argument("--viewer", action="store_true", help="Show the MuJoCo viewer")
    parser.add_argument("--object-width", type=float, default=None,
                        help="Simulate an object this wide [m] for grasp()")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    for label, port in (
        ("robot", args.robot_port),
        ("state stream", args.state_stream_port),
        ("gripper", args.gripper_port),
    ):
        if not _port_free(port):
            raise SystemExit(
                f"Port {port} ({label}) is already in use. Stop the process using it "
                "(a real RobotServer/GripperServer, or another mock) or pick other "
                "ports with --robot-port/--state-stream-port/--gripper-port."
            )

    robot = MockRobotServer(
        fci_ip="sim",
        cmd_port=args.robot_port,
        state_poll_hz=args.poll_hz,
        state_stream_port=args.state_stream_port,
        sim_set_hz=args.sim_set_hz,
        viewer=args.viewer,
    )
    gripper = MockGripperServer(
        "sim",
        cmd_port=args.gripper_port,
        object_width=args.object_width,
    )

    stop = threading.Event()

    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down ...", sig)
        robot._running = False
        gripper._running = False
        stop.set()

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    gripper.start()
    threads = [
        threading.Thread(target=robot.run, daemon=True, name="mock-robot"),
        threading.Thread(target=gripper.run, daemon=True, name="mock-gripper"),
    ]
    for thread in threads:
        thread.start()

    logger.info(
        "Mock stack up: robot %d, state stream %d, gripper %d (Ctrl+C to stop)",
        args.robot_port, args.state_stream_port, args.gripper_port,
    )
    stop.wait()
    for thread in threads:
        thread.join(timeout=5.0)
    logger.info("Mock stack stopped.")


if __name__ == "__main__":
    main()
