"""Franka Robot ZMQ Server.

Runs on the control machine. Wraps aiofranka.FrankaRemoteController with a
ZMQ ROUTER socket so the algorithm machine can control the robot remotely.

Two threads:
  - Main thread:  ZMQ ROUTER, receives commands and sends responses
  - Controller thread: owns FrankaRemoteController exclusively, processes
    commands from queue, polls state during idle time

Thread safety:
  Only the controller thread (and its temporary helper threads) access
  self._controller. The main thread never touches the controller directly.
  State cache is protected by _state_lock.

Usage:
    python -m franka_control.robot --fci-ip 192.168.0.2
"""

from __future__ import annotations

import argparse
import glob
import logging
import os
import queue
import signal
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

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
DEFAULT_CONTROLLER_TYPE = "pid"


# ── Data structures ──────────────────────────────────────────────

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


@dataclass
class _QueuedCommand:
    """Command queued for controller thread."""
    name: str
    params: dict
    event: threading.Event = field(default_factory=threading.Event)
    result: dict | None = None


class RobotServer:
    """ZMQ server for Franka robot control via aiofranka.

    Architecture:
      - Main thread: ZMQ recv/send only, never touches controller
      - Controller thread: owns FrankaRemoteController exclusively,
        processes commands from queue, polls state during idle

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
        self._state_interval = 1.0 / max(1.0, min(float(state_poll_hz), 200.0))

        # Controller — only accessed by controller thread (+ its helpers)
        self._controller: Optional[FrankaRemoteController] = None
        self._connected = False

        # Command queue — main thread writes, controller thread reads
        self._cmd_queue: queue.Queue[_QueuedCommand] = queue.Queue()
        self._cmd_event = threading.Event()

        # Blocking op — main thread sets _busy=True, controller thread clears
        self._busy = False
        self._worker_result: dict | None = None
        self._blocking_thread: Optional[threading.Thread] = None

        # Cached state — controller thread writes, main thread reads
        self._cached_state = CachedRobotState()
        self._state_lock = threading.Lock()

        # Lifecycle
        self._running = False
        self._ctx: Optional[zmq.Context] = None
        self._cmd_socket = None

    # ── Lifecycle ────────────────────────────────────────────────

    def run(self) -> None:
        """Start ZMQ socket and run main command loop."""
        self._ctx = zmq.Context()
        self._cmd_socket = self._ctx.socket(zmq.ROUTER)
        self._cmd_socket.bind(f"tcp://*:{self.cmd_port}")
        self._cmd_socket.setsockopt(zmq.RCVTIMEO, 200)
        self._running = True

        logger.info("Robot server listening on port %d", self.cmd_port)

        # Start controller thread
        ctrl_thread = threading.Thread(
            target=self._controller_loop, daemon=True, name="controller",
        )
        ctrl_thread.start()

        # Main command loop — ZMQ recv/send only
        while self._running:
            try:
                parts = self._cmd_socket.recv_multipart()
            except zmq.Again:
                continue
            if len(parts) < 3:
                continue

            identity = parts[0]
            response = self._dispatch(parts[2])
            packed = msgpack.packb(response, use_bin_type=True)
            self._cmd_socket.send_multipart([identity, b"", packed])

        # Shutdown: tell controller thread to exit, then clean up
        self._cmd_event.set()
        ctrl_thread.join(timeout=5.0)
        self._cleanup_zmq()

    def _cleanup_zmq(self) -> None:
        """Close ZMQ resources."""
        if self._cmd_socket is not None:
            try:
                self._cmd_socket.close()
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

    # ── Main thread: dispatch ─────────────────────────────────────

    def _dispatch(self, raw: bytes) -> dict:
        """Route a ZMQ message to the appropriate handler.

        Called on main thread. Never touches self._controller.
        """
        try:
            msg = msgpack.unpackb(raw, raw=False)
        except Exception:
            return {"success": False, "error": "Invalid msgpack"}

        command = msg.get("command", "")
        params = msg.get("params", {})

        # ---- Main-thread-only (no controller access) ----
        if command == "get_state":
            return self._handle_get_state()
        if command == "shutdown":
            self._running = False
            return {"success": True}

        # ---- Interrupt commands (bypass busy check) ----
        if command in ("stop", "disconnect"):
            return self._enqueue(command, params)

        # ---- Blocking commands ----
        if command in ("connect", "move", "start"):
            if self._busy:
                return {"success": False, "error": "Worker busy"}
            self._busy = True
            self._worker_result = None
            return self._enqueue(command, params, blocking=True)

        # ---- Fast commands ----
        if command in ("switch", "set", "is_running"):
            if self._busy:
                return {"success": False, "error": "Worker busy"}
            return self._enqueue(command, params)

        return {"success": False, "error": f"Unknown command: {command}"}

    def _handle_get_state(self) -> dict:
        """Return cached state + worker status. Main thread only."""
        worker_status = "busy" if self._busy else "idle"

        if not self._connected:
            return {
                "success": True,
                "state": {"worker_status": worker_status},
                "result": self._worker_result,
            }

        with self._state_lock:
            state_dict = self._cached_state.to_dict()

        state_dict["worker_status"] = worker_status
        return {"success": True, "state": state_dict, "result": self._worker_result}

    def _enqueue(self, command: str, params: dict, blocking: bool = False) -> dict:
        """Put command in queue for controller thread.

        For blocking commands: returns immediately with {"accepted": True}.
        For fast/interrupt commands: waits for controller thread to finish.
        """
        cmd = _QueuedCommand(command, params)
        self._cmd_queue.put(cmd)
        self._cmd_event.set()

        if blocking:
            return {"success": True, "accepted": True}

        # Wait for controller thread to process
        cmd.event.wait(timeout=10.0)
        if cmd.result is None:
            return {"success": False, "error": "Controller thread timeout"}
        return cmd.result

    # ── Controller thread ─────────────────────────────────────────

    def _controller_loop(self) -> None:
        """Controller thread main loop. Owns self._controller exclusively.

        Cycle:
          1. Process all pending commands from queue
          2. Check if blocking helper finished
          3. Poll state if idle
        """
        while self._running:
            self._cmd_event.wait(timeout=self._state_interval)
            self._cmd_event.clear()

            # 1. Process all pending commands
            while True:
                try:
                    cmd = self._cmd_queue.get_nowait()
                except queue.Empty:
                    break
                self._process_command(cmd)

            # 2. Check if blocking helper finished naturally
            if self._blocking_thread is not None:
                if not self._blocking_thread.is_alive():
                    self._blocking_thread.join()
                    self._blocking_thread = None
                    self._busy = False

            # 3. Poll state when idle
            if self._controller is not None and not self._busy:
                self._poll_state()

        # Cleanup controller on exit
        self._destroy_controller()

    def _process_command(self, cmd: _QueuedCommand) -> None:
        """Dispatch a queued command. Called on controller thread."""
        name = cmd.name

        if name == "connect":
            # Connect runs directly on controller thread (not helper).
            # FrankaRemoteController's subprocess/ZMQ/SharedMemory must be
            # created on the same thread that will use them for state polling.
            # Connect is a one-time operation that doesn't need stop interrupt.
            self._execute_blocking_inline(cmd)
        elif name in ("move", "start"):
            self._spawn_blocking(cmd)
        elif name == "stop":
            self._handle_stop(cmd)
        elif name == "disconnect":
            self._handle_disconnect(cmd)
        else:
            self._execute_fast(cmd)

    # ── Blocking operations ─────────────────────────────────────────

    def _execute_blocking_inline(self, cmd: _QueuedCommand) -> None:
        """Execute a blocking command directly on the controller thread.

        Used for connect — the FrankaRemoteController must be created on
        the same thread that polls state, to avoid cross-thread resource issues.
        Blocks the controller thread, but connect is one-time and doesn't
        need stop interrupt.
        """
        try:
            result = self._call_controller(cmd.name, cmd.params)
            self._worker_result = result
        except Exception as e:
            logger.exception("Blocking op '%s' failed", cmd.name)
            self._worker_result = {"success": False, "error": str(e)}
        self._busy = False
        cmd.result = self._worker_result
        cmd.event.set()

    def _spawn_blocking(self, cmd: _QueuedCommand) -> None:
        """Spawn a helper thread for a blocking controller call.

        The controller thread stays free to process stop/disconnect.
        """
        def _helper():
            try:
                result = self._call_controller(cmd.name, cmd.params)
                self._worker_result = result
            except Exception as e:
                logger.exception("Blocking op '%s' failed", cmd.name)
                self._worker_result = {"success": False, "error": str(e)}

        self._blocking_thread = threading.Thread(
            target=_helper, daemon=True, name=f"helper-{cmd.name}",
        )
        self._blocking_thread.start()

    # ── Interrupt handlers ────────────────────────────────────────

    def _handle_stop(self, cmd: _QueuedCommand) -> None:
        """Stop controller and kill any blocking op. Controller thread only."""
        # Kill helper if running
        if self._blocking_thread is not None and self._blocking_thread.is_alive():
            if self._controller is not None:
                try:
                    self._controller.stop()
                except Exception:
                    pass
            self._blocking_thread.join(timeout=5.0)
            if self._blocking_thread.is_alive():
                logger.error(
                    "Helper thread did not stop in time, "
                    "shutting down server"
                )
                self._running = False
                cmd.result = {"success": False, "error": "Blocking op did not stop in time, server shutting down"}
                cmd.event.set()
                return
            self._blocking_thread = None
        # Always stop the controller itself (stops PID/OSC control loop)
        elif self._controller is not None:
            try:
                self._controller.stop()
            except Exception:
                pass

        self._busy = False
        self._worker_result = None
        cmd.result = {"success": True}
        cmd.event.set()

    def _handle_disconnect(self, cmd: _QueuedCommand) -> None:
        """Stop, destroy controller, clean up. Controller thread only."""
        # Interrupt any running blocking op
        if self._blocking_thread is not None and self._blocking_thread.is_alive():
            if self._controller is not None:
                try:
                    self._controller.stop()
                except Exception:
                    pass
            self._blocking_thread.join(timeout=5.0)
            if self._blocking_thread.is_alive():
                # Helper won't die — server is compromised, shut down
                logger.error(
                    "Helper thread did not stop in time during disconnect, "
                    "shutting down server"
                )
                self._running = False
                cmd.result = {"success": False, "error": "Blocking op did not stop in time, server shutting down"}
                cmd.event.set()
                return
            self._blocking_thread = None

        self._destroy_controller()
        self._busy = False
        self._worker_result = None
        cmd.result = {"success": True}
        cmd.event.set()

    # ── Fast command execution ────────────────────────────────────

    def _execute_fast(self, cmd: _QueuedCommand) -> None:
        """Execute a non-blocking command. Controller thread only."""
        try:
            cmd.result = self._call_controller(cmd.name, cmd.params)
        except Exception as e:
            logger.exception("Fast command '%s' failed", cmd.name)
            cmd.result = {"success": False, "error": str(e)}
        cmd.event.set()

    # ── Controller calls (all on controller thread or its helper) ─

    def _call_controller(self, name: str, params: dict) -> dict:
        """Execute a single controller operation. Never called from main thread."""
        if name == "connect":
            return self._do_connect(params)
        if name == "move":
            return self._do_move(params)
        if name == "start":
            return self._do_start(params)
        if name == "switch":
            return self._do_switch(params)
        if name == "set":
            return self._do_set(params)
        if name == "is_running":
            return self._do_is_running(params)
        return {"success": False, "error": f"Unknown controller call: {name}"}

    def _do_connect(self, params: dict) -> dict:
        if FrankaRemoteController is None:
            raise RuntimeError("aiofranka is not installed")

        self._clean_ipc_sockets()

        ctrl = FrankaRemoteController(self._fci_ip, home=False)
        try:
            ctrl.start()
            controller_type = params.get("controller_type", DEFAULT_CONTROLLER_TYPE)
            ctrl.switch(controller_type)

            if not ctrl.running:
                raise RuntimeError(
                    f"Controller died after switch to '{controller_type}'"
                )
        except Exception:
            try:
                ctrl.stop()
            except Exception:
                pass
            raise

        self._controller = ctrl
        self._connected = True
        return {"success": True}

    def _do_move(self, params: dict) -> dict:
        if self._controller is None:
            raise RuntimeError("Not connected")
        qpos = np.frombuffer(params["qpos"], dtype=np.float64)
        self._controller.move(qpos)
        return {"success": True}

    def _do_start(self, params: dict) -> dict:
        if self._controller is None:
            raise RuntimeError("Not connected")
        self._controller.start()
        return {"success": True}

    def _do_switch(self, params: dict) -> dict:
        ctrl_type = params.get("type")
        if not ctrl_type:
            return {"success": False, "error": "type is required"}
        if self._controller is None:
            return {"success": False, "error": "Not connected"}
        self._controller.switch(ctrl_type)
        return {"success": True}

    def _do_set(self, params: dict) -> dict:
        attr = params.get("attr")
        if not attr:
            return {"success": False, "error": "attr is required"}
        value_bytes = params.get("value")
        if value_bytes is None:
            return {"success": False, "error": "value is required"}
        if self._controller is None:
            return {"success": False, "error": "Not connected"}

        value = np.frombuffer(value_bytes, dtype=np.float64)
        shape = params.get("shape", [])
        if shape:
            value = value.reshape(shape)
        self._controller.set(attr, value)
        return {"success": True}

    def _do_is_running(self, params: dict) -> dict:
        if self._controller is None:
            return {"success": True, "running": False}
        return {"success": True, "running": self._controller.running}

    # ── Helpers ───────────────────────────────────────────────────

    def _poll_state(self) -> None:
        """Read controller.state and update cache. Controller thread only."""
        try:
            state = self._controller.state
            if state is not None:
                with self._state_lock:
                    self._cached_state.update(state)
        except Exception as e:
            logger.warning("State poll failed: %s", e)

    def _destroy_controller(self) -> None:
        """Stop and release controller. Controller thread only."""
        if self._controller is not None:
            try:
                self._controller.stop()
            except Exception:
                pass
            self._controller = None
        self._connected = False
        self._clean_ipc_sockets()

    def _clean_ipc_sockets(self) -> None:
        """Remove stale aiofranka IPC socket files."""
        pattern = f"/tmp/aiofranka_{self._fci_ip.replace('.', '_')}*"
        for f in glob.glob(pattern):
            try:
                os.remove(f)
                logger.info("Removed stale IPC socket: %s", f)
            except OSError:
                pass


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
