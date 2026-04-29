"""Franka Gripper ZMQ Server.

Runs on the control machine. Wraps pylibfranka.Gripper with a ZMQ ROUTER
socket so the algorithm machine can control the gripper remotely.

Three threads:
  - Main thread:  ZMQ ROUTER, receives commands and sends responses
  - Worker thread: executes blocking pylibfranka calls (move/grasp/homing/stop)
  - State thread:  polls readOnce() at configurable Hz, caches result

Usage:
    python -m franka_control.gripper.gripper_server --robot-ip 172.16.0.2
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import msgpack
import zmq

try:
    import pylibfranka
except ImportError:
    pylibfranka = None

logger = logging.getLogger(__name__)


# ── Message protocol ─────────────────────────────────────────────
# All messages are dicts serialized with msgpack.
#
# Command (client → server):
#   {"command": str, "params": dict}
#
# Response (server → client):
#   {"success": bool, "error": str | None, "state": dict | None}


# ── Constants ────────────────────────────────────────────────────

# Franka Hand official specs:
#   Max opening width:  80 mm (0.08 m)
#   Max speed:          0.10 m/s (total travel)
#   Continuous force:   70 N
#   Max grasping force: 140 N

# Defaults (conservative)
DEFAULT_SPEED = 0.1        # m/s (== max speed)
DEFAULT_FORCE = 40.0       # N   (< continuous 70 N)
DEFAULT_OPEN_WIDTH = 0.08  # m   (== max width)

# Server defaults
DEFAULT_CMD_PORT = 5556
DEFAULT_STATE_POLL_HZ = 50.0


class GripperStatus(str, Enum):
    """Worker thread status."""
    IDLE = "idle"
    BUSY = "busy"


@dataclass
class CachedState:
    """Thread-safe cached gripper state."""
    width: float = 0.0
    max_width: float = 0.0
    is_grasped: bool = False
    temperature: int = 0

    def to_dict(self) -> dict:
        return {
            "width": self.width,
            "max_width": self.max_width,
            "is_grasped": self.is_grasped,
            "temperature": self.temperature,
        }

    def update(self, width: float, max_width: float,
               is_grasped: bool, temperature: int) -> None:
        self.width = width
        self.max_width = max_width
        self.is_grasped = is_grasped
        self.temperature = temperature


class GripperServer:
    """ZMQ server for Franka native gripper control.

    Args:
        robot_ip: Franka robot IP address.
        cmd_port: ZMQ ROUTER socket port.
        state_poll_hz: Background state polling frequency (default: 50 Hz).
    """

    def __init__(
        self,
        robot_ip: str,
        cmd_port: int = DEFAULT_CMD_PORT,
        state_poll_hz: float = DEFAULT_STATE_POLL_HZ,
    ):
        self.robot_ip = robot_ip
        self.cmd_port = cmd_port
        self.state_poll_hz = max(1.0, min(float(state_poll_hz), 200.0))
        self._state_interval = 1.0 / self.state_poll_hz

        # pylibfranka Gripper (created in start())
        self._gripper: Any = None

        # Cached state
        self._cached_state = CachedState()
        self._state_lock = threading.Lock()

        # Worker thread state
        self._worker_lock = threading.Lock()
        self._worker_status = GripperStatus.IDLE
        self._worker_result: dict | None = None  # result of last job
        self._worker_thread: threading.Thread | None = None
        self._stop_flag = False

        # Homing protection (prevents state polling during homing)
        self._homing_lock = threading.Lock()
        self._homing_in_progress = False

        # ZMQ
        self._ctx: zmq.Context | None = None
        self._cmd_socket = None

        # Lifecycle
        self._running = False
        self._state_thread: threading.Thread | None = None

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        """Connect to gripper, start ZMQ socket and state polling."""
        if pylibfranka is None:
            raise RuntimeError("pylibfranka is not installed")

        logger.info("Connecting to gripper at %s ...", self.robot_ip)
        self._gripper = pylibfranka.Gripper(self.robot_ip)
        logger.info("Gripper connected.")

        # ZMQ ROUTER socket
        self._ctx = zmq.Context()
        self._cmd_socket = self._ctx.socket(zmq.ROUTER)
        self._cmd_socket.bind(f"tcp://*:{self.cmd_port}")
        self._cmd_socket.setsockopt(zmq.RCVTIMEO, 200)
        logger.info("Gripper server listening on port %d", self.cmd_port)

        # State polling thread
        self._running = True
        self._state_thread = threading.Thread(
            target=self._state_poll_loop, daemon=True
        )
        self._state_thread.start()

    def run(self) -> None:
        """Main loop: receive and handle commands until shutdown."""
        while self._running:
            try:
                # ROUTER recv: [identity, delimiter, data]
                parts = self._cmd_socket.recv_multipart()
            except zmq.Again:
                continue  # timeout, check _running

            if len(parts) < 3:
                continue

            identity = parts[0]
            # parts[1] is delimiter
            data = parts[2]

            response = self._dispatch(data)
            packed = msgpack.packb(response, use_bin_type=True)
            self._cmd_socket.send_multipart([identity, b"", packed])

        self._cleanup()

    def _cleanup(self) -> None:
        """Clean up all resources."""
        self._running = False

        if self._state_thread and self._state_thread.is_alive():
            self._state_thread.join(timeout=2.0)

        for sock in (self._cmd_socket,):
            if sock is not None:
                try:
                    sock.close()
                except Exception:
                    pass
        self._cmd_socket = None

        if self._ctx is not None:
            try:
                self._ctx.term()
            except Exception:
                pass
            self._ctx = None

        logger.info("Gripper server stopped.")

    # ── Command dispatch ─────────────────────────────────────────

    def _dispatch(self, raw: bytes) -> dict:
        """Parse msgpack command and route to handler."""
        try:
            msg = msgpack.unpackb(raw, raw=False)
        except Exception:
            return {"success": False, "error": "Invalid msgpack"}

        command = msg.get("command", "")
        params = msg.get("params", {})

        handlers = {
            "homing": self._cmd_homing,
            "open": self._cmd_open,
            "move": self._cmd_move,
            "grasp": self._cmd_grasp,
            "stop": self._cmd_stop,
            "get_state": self._cmd_get_state,
            "shutdown": self._cmd_shutdown,
        }

        handler = handlers.get(command)
        if handler is None:
            return {"success": False, "error": f"Unknown command: {command}"}

        try:
            return handler(params)
        except Exception as e:
            logger.exception("Error handling '%s'", command)
            return {"success": False, "error": str(e)}

    # ── Command handlers ─────────────────────────────────────────

    def _cmd_get_state(self, params: dict) -> dict:
        """Return cached state and last worker result."""
        with self._state_lock:
            state = self._cached_state.to_dict()
        with self._worker_lock:
            state["status"] = self._worker_status.value
            result = self._worker_result
        return {"success": True, "state": state, "result": result}

    def _cmd_homing(self, params: dict) -> dict:
        return self._submit_job("homing", self._do_homing)

    def _do_homing(self):
        """Execute homing with state polling paused."""
        with self._homing_lock:
            self._homing_in_progress = True
        try:
            logger.info("Homing started (state polling paused)")
            result = self._gripper.homing()
            logger.info("Homing completed")
            return result
        finally:
            with self._homing_lock:
                self._homing_in_progress = False

    def _cmd_open(self, params: dict) -> dict:
        width = float(params.get("width", DEFAULT_OPEN_WIDTH))
        speed = float(params.get("speed", DEFAULT_SPEED))
        return self._submit_job("open", lambda: self._gripper.move(width, speed))

    def _cmd_move(self, params: dict) -> dict:
        """Pure position move (no force control)."""
        width = float(params.get("width", DEFAULT_OPEN_WIDTH))
        speed = float(params.get("speed", DEFAULT_SPEED))
        return self._submit_job("move", lambda: self._gripper.move(width, speed))

    def _cmd_grasp(self, params: dict) -> dict:
        return self._submit_job("grasp", lambda: self._gripper.grasp(
            width=float(params.get("width", 0.02)),
            speed=float(params.get("speed", DEFAULT_SPEED)),
            force=float(params.get("force", DEFAULT_FORCE)),
            epsilon_inner=float(params.get("epsilon_inner", 0.005)),
            epsilon_outer=float(params.get("epsilon_outer", 0.005)),
        ))

    def _cmd_stop(self, params: dict) -> dict:
        """Stop gripper physically and cancel any running job.

        Order: set stop flag → physical stop (unblocks pylibfranka call)
        → wait for worker thread → reset state.
        """
        self._stop_flag = True
        try:
            self._gripper.stop()
        except Exception:
            pass  # physical stop may fail if gripper already idle
        with self._worker_lock:
            if self._worker_thread and self._worker_thread.is_alive():
                self._worker_thread.join(timeout=2.0)
            self._worker_status = GripperStatus.IDLE
            self._worker_result = None
            self._worker_thread = None
            self._stop_flag = False
        return {"success": True}

    def _cmd_shutdown(self, params: dict) -> dict:
        self._running = False
        return {"success": True}

    # ── Worker job submission ────────────────────────────────────

    def _submit_job(self, name: str, fn) -> dict:
        """Submit a blocking job to the worker thread.

        Returns immediately with accepted/rejected.
        The job runs in a background thread; client polls get_state
        to check when it finishes.
        """
        with self._worker_lock:
            if self._worker_status == GripperStatus.BUSY:
                return {"success": False, "error": "Gripper busy"}
            self._worker_status = GripperStatus.BUSY
            self._worker_result = None

        def _run():
            try:
                result = fn()
                with self._worker_lock:
                    # Skip writing result if stop was requested
                    if not self._stop_flag:
                        self._worker_result = {
                            "success": True if result is None else bool(result),
                        }
                    # Always reset status (even if stopped)
                    self._worker_status = GripperStatus.IDLE
            except Exception as e:
                with self._worker_lock:
                    if not self._stop_flag:
                        self._worker_result = {"success": False, "error": str(e)}
                    # Always reset status (even if stopped)
                    self._worker_status = GripperStatus.IDLE

        t = threading.Thread(target=_run, daemon=True)
        self._worker_thread = t
        t.start()
        return {"success": True, "accepted": True}

    # ── State polling ────────────────────────────────────────────

    def _poll_state_once(self) -> None:
        """Read gripper state once and update cache.

        Skips polling during homing to avoid interrupting the calibration.
        """
        # Check if homing is in progress
        with self._homing_lock:
            if self._homing_in_progress:
                return  # Skip state polling during homing

        try:
            s = self._gripper.read_once()
            with self._state_lock:
                self._cached_state.update(
                    width=float(s.width),
                    max_width=float(s.max_width),
                    is_grasped=bool(s.is_grasped),
                    temperature=int(s.temperature),
                )
        except Exception as e:
            logger.warning("State poll failed: %s", e)

    def _state_poll_loop(self) -> None:
        """Background thread: poll gripper state at configured Hz."""
        while self._running:
            t0 = time.monotonic()
            self._poll_state_once()
            elapsed = time.monotonic() - t0
            remaining = self._state_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)

    # ── Entry point ──────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Franka Gripper ZMQ Server")
    parser.add_argument("--robot-ip", required=True, help="Franka robot IP")
    parser.add_argument("--port", type=int, default=DEFAULT_CMD_PORT,
                        help=f"ZMQ port (default: {DEFAULT_CMD_PORT})")
    parser.add_argument("--poll-hz", type=float, default=DEFAULT_STATE_POLL_HZ,
                        help=f"State poll Hz (default: {DEFAULT_STATE_POLL_HZ})")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    server = GripperServer(args.robot_ip, cmd_port=args.port,
                           state_poll_hz=args.poll_hz)

    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down ...", sig)
        server._running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    server.start()
    server.run()


if __name__ == "__main__":
    main()
