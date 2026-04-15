"""Franka Robot ZMQ Server.

Runs on the control machine. Wraps aiofranka.FrankaRemoteController with a
ZMQ ROUTER socket so the algorithm machine can control the robot remotely.

Three threads:
  - Main thread:  ZMQ ROUTER, receives commands and sends responses
  - Worker thread: executes blocking aiofranka calls (connect/move/start)
  - State thread:  polls controller.state at configurable Hz, caches result

Usage:
    python -m franka_control.robot --fci-ip 192.168.0.2
"""

from __future__ import annotations

import argparse
import logging
import signal
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

import msgpack
import numpy as np
import zmq

try:
    from aiofranka import FrankaRemoteController
except ImportError:
    FrankaRemoteController = None

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────

DEFAULT_CMD_PORT = 5555
DEFAULT_STATE_POLL_HZ = 50.0
DEFAULT_CONTROLLER_TYPE = "pid"  # initial controller after connect


class WorkerStatus(str, Enum):
    IDLE = "idle"
    BUSY = "busy"


@dataclass
class CachedRobotState:
    """Thread-safe cached robot state (serialized from SharedMemory)."""
    qpos: np.ndarray = field(default_factory=lambda: np.zeros(7))
    qvel: np.ndarray = field(default_factory=lambda: np.zeros(7))
    ee: np.ndarray = field(default_factory=lambda: np.eye(4))
    jac: np.ndarray = field(default_factory=lambda: np.zeros((6, 7)))
    mm: np.ndarray = field(default_factory=lambda: np.zeros((7, 7)))
    last_torque: np.ndarray = field(default_factory=lambda: np.zeros(7))
    q_desired: np.ndarray = field(default_factory=lambda: np.zeros(7))
    timestamp: float = 0.0

    def to_dict(self) -> dict:
        return {
            "qpos": self.qpos.tobytes(),
            "qvel": self.qvel.tobytes(),
            "ee": self.ee.tobytes(),
            "jac": self.jac.tobytes(),
            "mm": self.mm.tobytes(),
            "last_torque": self.last_torque.tobytes(),
            "q_desired": self.q_desired.tobytes(),
            "timestamp": self.timestamp,
            # Shapes for deserialization
            "shapes": {
                "qpos": list(self.qpos.shape),
                "qvel": list(self.qvel.shape),
                "ee": list(self.ee.shape),
                "jac": list(self.jac.shape),
                "mm": list(self.mm.shape),
                "last_torque": list(self.last_torque.shape),
                "q_desired": list(self.q_desired.shape),
            },
        }

    def update(self, state: dict) -> None:
        """Update from aiofranka SharedMemory state dict."""
        self.qpos = np.array(state["qpos"], dtype=np.float64)
        self.qvel = np.array(state["qvel"], dtype=np.float64)
        self.ee = np.array(state["ee"], dtype=np.float64)
        self.jac = np.array(state["jac"], dtype=np.float64)
        self.mm = np.array(state["mm"], dtype=np.float64)
        self.last_torque = np.array(state["last_torque"], dtype=np.float64)
        self.q_desired = np.array(state["q_desired"], dtype=np.float64)
        self.timestamp = float(state.get("timestamp", 0.0))


class RobotServer:
    """ZMQ server for Franka robot control via aiofranka.

    Args:
        fci_ip: Franka robot FCI IP address (server-side config).
        cmd_port: ZMQ ROUTER socket port.
        state_poll_hz: Background state polling frequency.
    """

    def __init__(
        self,
        fci_ip: str,
        cmd_port: int = DEFAULT_CMD_PORT,
        state_poll_hz: float = DEFAULT_STATE_POLL_HZ,
    ):
        self._fci_ip = fci_ip
        self.cmd_port = cmd_port
        self.state_poll_hz = max(1.0, min(float(state_poll_hz), 200.0))
        self._state_interval = 1.0 / self.state_poll_hz

        # aiofranka controller (created on 'connect' command)
        self._controller: Optional[FrankaRemoteController] = None

        # Cached state
        self._cached_state = CachedRobotState()
        self._state_lock = threading.Lock()

        # Worker thread state
        self._worker_lock = threading.Lock()
        self._worker_status = WorkerStatus.IDLE
        self._worker_result: dict | None = None
        self._worker_thread: threading.Thread | None = None
        self._stop_flag = False

        # ZMQ
        self._ctx: Optional[zmq.Context] = None
        self._cmd_socket = None

        # Lifecycle
        self._running = False
        self._state_thread: Optional[threading.Thread] = None

    # ── Lifecycle ────────────────────────────────────────────────

    def run(self) -> None:
        """Start ZMQ socket and run main command loop."""
        self._ctx = zmq.Context()
        self._cmd_socket = self._ctx.socket(zmq.ROUTER)
        self._cmd_socket.bind(f"tcp://*:{self.cmd_port}")
        self._cmd_socket.setsockopt(zmq.RCVTIMEO, 200)
        self._running = True

        logger.info("Robot server listening on port %d", self.cmd_port)

        # State polling thread
        self._state_thread = threading.Thread(
            target=self._state_poll_loop, daemon=True,
        )
        self._state_thread.start()

        # Main command loop
        while self._running:
            try:
                parts = self._cmd_socket.recv_multipart()
            except zmq.Again:
                continue

            if len(parts) < 3:
                continue

            identity = parts[0]
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

        if self._controller is not None:
            try:
                self._controller.stop()
            except Exception:
                pass
            self._controller = None

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

        logger.info("Robot server stopped.")

    # ── Command dispatch ─────────────────────────────────────────

    def _dispatch(self, raw: bytes) -> dict:
        try:
            msg = msgpack.unpackb(raw, raw=False)
        except Exception:
            return {"success": False, "error": "Invalid msgpack"}

        command = msg.get("command", "")
        params = msg.get("params", {})

        handlers = {
            "connect": self._cmd_connect,
            "disconnect": self._cmd_disconnect,
            "switch": self._cmd_switch,
            "set": self._cmd_set,
            "move": self._cmd_move,
            "get_state": self._cmd_get_state,
            "start": self._cmd_start,
            "stop": self._cmd_stop,
            "is_running": self._cmd_is_running,
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

    def _cmd_connect(self, params: dict) -> dict:
        """Create FrankaRemoteController, start(), switch(). Blocking.

        Uses fci_ip from server config, not from client params.
        """
        if self._controller is not None:
            return {"success": False, "error": "Already connected"}

        controller_type = params.get("controller_type", DEFAULT_CONTROLLER_TYPE)

        def _do_connect():
            if FrankaRemoteController is None:
                raise RuntimeError("aiofranka is not installed")

            ctrl = FrankaRemoteController(self._fci_ip, home=False)
            ctrl.start()
            ctrl.switch(controller_type)
            return ctrl

        return self._submit_job("connect", _do_connect)

    def _cmd_disconnect(self, params: dict) -> dict:
        """Stop controller and clean up."""
        if self._controller is not None:
            try:
                self._controller.stop()
            except Exception:
                pass
            self._controller = None
        return {"success": True}

    def _cmd_switch(self, params: dict) -> dict:
        """Switch controller type (pid/osc/impedance/torque)."""
        if self._controller is None:
            return {"success": False, "error": "Not connected"}
        ctrl_type = params.get("type")
        if not ctrl_type:
            return {"success": False, "error": "type is required"}
        self._controller.switch(ctrl_type)
        return {"success": True}

    def _cmd_set(self, params: dict) -> dict:
        """Set a target attribute (q_desired / ee_desired / torque)."""
        if self._controller is None:
            return {"success": False, "error": "Not connected"}

        attr = params.get("attr")
        if not attr:
            return {"success": False, "error": "attr is required"}

        value_bytes = params.get("value")
        shape = params.get("shape", [])
        if value_bytes is None:
            return {"success": False, "error": "value is required"}

        value = np.frombuffer(value_bytes, dtype=np.float64)
        if shape:
            value = value.reshape(shape)

        self._controller.set(attr, value)
        return {"success": True}

    def _cmd_move(self, params: dict) -> dict:
        """Ruckig move to target joint position. Blocking."""
        if self._controller is None:
            return {"success": False, "error": "Not connected"}

        qpos_bytes = params.get("qpos")
        if qpos_bytes is None:
            return {"success": False, "error": "qpos is required"}

        qpos = np.frombuffer(qpos_bytes, dtype=np.float64)

        def _do_move():
            self._controller.move(qpos)

        return self._submit_job("move", _do_move)

    def _cmd_get_state(self, params: dict) -> dict:
        """Return cached state (no SharedMemory access on main thread).

        Returns worker_status even when controller is None, so client can
        poll during connect without getting a spurious 'Not connected' error.
        """
        with self._worker_lock:
            worker_status = self._worker_status.value
            result = self._worker_result

        if self._controller is None:
            return {
                "success": True,
                "state": {"worker_status": worker_status},
                "result": result,
            }

        with self._state_lock:
            state_dict = self._cached_state.to_dict()

        state_dict["worker_status"] = worker_status
        return {"success": True, "state": state_dict, "result": result}

    def _cmd_start(self, params: dict) -> dict:
        """Start controller. Blocking."""
        if self._controller is None:
            return {"success": False, "error": "Not connected"}

        def _do_start():
            self._controller.start()

        return self._submit_job("start", _do_start)

    def _cmd_stop(self, params: dict) -> dict:
        """Stop controller."""
        if self._controller is None:
            return {"success": False, "error": "Not connected"}

        # Stop may need to interrupt a blocking move
        self._stop_flag = True
        try:
            self._controller.stop()
        except Exception:
            pass

        # Join worker WITHOUT holding _worker_lock,
        # so the worker can acquire it to finish writing its result.
        thread_to_join = self._worker_thread
        if thread_to_join and thread_to_join.is_alive():
            thread_to_join.join(timeout=2.0)

        with self._worker_lock:
            self._worker_status = WorkerStatus.IDLE
            self._worker_result = None
            self._worker_thread = None
            self._stop_flag = False

        return {"success": True}

    def _cmd_is_running(self, params: dict) -> dict:
        """Check if controller is running."""
        if self._controller is None:
            return {"success": True, "running": False}
        return {"success": True, "running": self._controller.running}

    def _cmd_shutdown(self, params: dict) -> dict:
        self._running = False
        return {"success": True}

    # ── Worker job submission ────────────────────────────────────

    def _submit_job(self, name: str, fn) -> dict:
        """Submit a blocking job to worker thread.

        For connect jobs, the worker stores the created controller.
        Returns immediately with accepted/rejected.
        """
        with self._worker_lock:
            if self._worker_status == WorkerStatus.BUSY:
                return {"success": False, "error": "Worker busy"}
            self._worker_status = WorkerStatus.BUSY
            self._worker_result = None

        def _run():
            try:
                result = fn()

                # Special handling for connect: store the controller
                if name == "connect" and result is not None:
                    self._controller = result

                with self._worker_lock:
                    if not self._stop_flag:
                        self._worker_result = {"success": True}
                        self._worker_status = WorkerStatus.IDLE
            except Exception as e:
                logger.exception("Worker job '%s' failed", name)
                with self._worker_lock:
                    if not self._stop_flag:
                        # If connect failed, ensure controller is None
                        if name == "connect":
                            self._controller = None
                        self._worker_result = {
                            "success": False,
                            "error": str(e),
                        }
                        self._worker_status = WorkerStatus.IDLE

        t = threading.Thread(target=_run, daemon=True)
        with self._worker_lock:
            self._worker_thread = t
        t.start()
        return {"success": True, "accepted": True}

    # ── State polling ────────────────────────────────────────────

    def _state_poll_loop(self) -> None:
        """Background thread: poll robot state from SharedMemory."""
        while self._running:
            t0 = time.monotonic()

            if self._controller is not None:
                try:
                    state = self._controller.state
                    if state is not None:
                        with self._state_lock:
                            self._cached_state.update(state)
                except Exception as e:
                    logger.warning("State poll failed: %s", e)

            elapsed = time.monotonic() - t0
            remaining = self._state_interval - elapsed
            if remaining > 0:
                time.sleep(remaining)


# ── Entry point ──────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Franka Robot ZMQ Server")
    parser.add_argument("--fci-ip", required=True,
                        help="Franka robot FCI IP address")
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

    server = RobotServer(fci_ip=args.fci_ip, cmd_port=args.port,
                         state_poll_hz=args.poll_hz)

    def _signal_handler(sig, frame):
        logger.info("Received signal %d, shutting down ...", sig)
        server._running = False

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    server.run()


if __name__ == "__main__":
    main()
