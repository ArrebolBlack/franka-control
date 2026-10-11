"""Mock RobotServer: the real ZMQ/msgpack protocol on a simulated FR3.

Subclasses the real ``RobotServer`` so command dispatch, threads, the state
stream and shutdown semantics are inherited verbatim; only the hardware-facing
pieces are replaced: the controller (aiofranka MuJoCo simulation instead of
``FrankaRemoteController``) and the FCI-specific error recovery / IPC cleanup.

Usage:
    python -m franka_control.mock.robot_server [--port 5555] [--viewer]
"""

from __future__ import annotations

import argparse
import logging
import signal

from franka_control.mock.sim_controller import SimControllerAdapter
from franka_control.robot.robot_server import (
    DEFAULT_CMD_PORT,
    DEFAULT_STATE_POLL_HZ,
    DEFAULT_STATE_STREAM_PORT,
    RobotServer,
)

logger = logging.getLogger(__name__)


class MockRobotServer(RobotServer):
    """RobotServer whose controller is a MuJoCo-simulated FR3 (no hardware)."""

    def __init__(self, *args, sim_set_hz: float = 50.0, viewer: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.sim_set_hz = sim_set_hz
        self.viewer = viewer

    def _make_controller(self) -> SimControllerAdapter:
        return SimControllerAdapter(set_hz=self.sim_set_hz, viewer=self.viewer)

    def _recover_errors(self) -> None:
        """No FCI error state in simulation."""

    def _clean_ipc_sockets(self) -> None:
        """No aiofranka subprocess sockets in simulation."""


def main():
    parser = argparse.ArgumentParser(
        description="Mock Franka Robot ZMQ Server (MuJoCo simulation, no hardware)"
    )
    parser.add_argument("--fci-ip", default="sim",
                        help="Unused (kept for CLI parity with the real server)")
    parser.add_argument("--port", type=int, default=DEFAULT_CMD_PORT,
                        help=f"ZMQ port (default: {DEFAULT_CMD_PORT})")
    parser.add_argument("--state-stream-port", type=int, default=DEFAULT_STATE_STREAM_PORT,
                        help=f"State stream port (default: {DEFAULT_STATE_STREAM_PORT})")
    parser.add_argument("--poll-hz", type=float, default=DEFAULT_STATE_POLL_HZ,
                        help=f"State poll Hz (default: {DEFAULT_STATE_POLL_HZ})")
    parser.add_argument("--sim-set-hz", type=float, default=50.0,
                        help="Rate limit for set(), mirroring the real stack (default: 50)")
    parser.add_argument("--viewer", action="store_true",
                        help="Show the MuJoCo viewer window")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    server = MockRobotServer(
        fci_ip=args.fci_ip,
        cmd_port=args.port,
        state_poll_hz=args.poll_hz,
        state_stream_port=args.state_stream_port,
        sim_set_hz=args.sim_set_hz,
        viewer=args.viewer,
    )

    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down ...", sig)
        server._running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    server.run()


if __name__ == "__main__":
    main()
