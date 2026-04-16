"""Franka Robot ZMQ Client.

Runs on the algorithm machine. Communicates with RobotServer via ZMQ.
Provides the same API as aiofranka.FrankaRemoteController but over TCP.

Usage:
    client = RobotClient(host="192.168.0.2")
    client.connect()  # server uses its own FCI IP config
    state = client.get_state()
    client.set("q_desired", target_qpos)
    client.close()
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import msgpack
import numpy as np
import zmq

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 60.0  # connect/start can take a long time
MOVE_TIMEOUT = 30.0
DEFAULT_STATE_STREAM_PORT = 5557


class RobotClient:
    """TCP client for remote Franka robot control via RobotServer.

    Mirrors the aiofranka.FrankaRemoteController API, but sends commands
    over ZMQ to a RobotServer running on the control machine.

    Args:
        host: RobotServer host (control machine IP).
        port: ZMQ port (default: 5555).
        timeout: Default timeout for blocking operations in seconds.
    """

    def __init__(
        self,
        host: str,
        port: int = 5555,
        state_stream_port: int = DEFAULT_STATE_STREAM_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self._state_stream_port = state_stream_port
        self.timeout = timeout

        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5s recv timeout
        self._socket.setsockopt(zmq.SNDTIMEO, 5000)   # 5s send timeout
        self._socket.connect(f"tcp://{host}:{port}")
        logger.info("Connected to robot server at %s:%d", host, port)

        self._pull_socket = self._ctx.socket(zmq.PULL)
        self._pull_socket.setsockopt(zmq.RCVHWM, 2)
        self._pull_socket.setsockopt(zmq.RCVTIMEO, 100)
        self._pull_socket.connect(f"tcp://{host}:{state_stream_port}")

        # Local state cache
        self._cached_state: dict | None = None
        self._streaming_state: dict | None = None
        self._state_lock = threading.Lock()
        self._stream_running = True
        self._state_thread = threading.Thread(
            target=self._state_receiver,
            daemon=True,
            name="state-receiver",
        )
        self._state_thread.start()

    # ── Low-level ────────────────────────────────────────────────

    def _send_command(self, command: str, params: dict = None) -> dict:
        """Send command and wait for response."""
        msg = {"command": command}
        if params:
            msg["params"] = params

        try:
            packed = msgpack.packb(msg, use_bin_type=True)
            self._socket.send_multipart([b"", packed])

            parts = self._socket.recv_multipart()
            if len(parts) < 2:
                return {"success": False, "error": "Malformed response"}
            return msgpack.unpackb(parts[-1], raw=False)
        except zmq.Again:
            logger.error("Timeout waiting for robot server response")
            return {"success": False, "error": "Server timeout"}
        except Exception as e:
            logger.exception("Robot command failed")
            return {"success": False, "error": str(e)}

    def _wait_until_idle(self, timeout: float) -> dict:
        """Poll get_state until worker becomes idle, return result."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = self._send_command("get_state")
            if not resp.get("success"):
                return resp
            state = resp.get("state", {})
            if state.get("worker_status") == "idle":
                result = resp.get("result")
                if result is not None:
                    return result
                return {"success": True}
            time.sleep(0.05)  # 20Hz polling
        return {"success": False, "error": "Timeout waiting for robot server"}

    def _decode_state(self, raw: dict) -> dict:
        """Decode msgpack state payload into numpy arrays."""
        shapes = raw.get("shapes", {})
        defaults = {
            "qpos": [7],
            "qvel": [7],
            "ee": [4, 4],
            "jac": [6, 7],
            "mm": [7, 7],
            "last_torque": [7],
            "q_desired": [7],
        }
        state = {}
        for key, default_shape in defaults.items():
            state[key] = np.frombuffer(raw[key], dtype=np.float64).copy().reshape(
                shapes.get(key, default_shape)
            )
        state["timestamp"] = raw.get("timestamp", 0.0)
        return state

    def _state_receiver(self) -> None:
        """Receive streamed state snapshots and keep only the latest."""
        while self._stream_running:
            try:
                raw = self._pull_socket.recv()
                while True:
                    try:
                        raw = self._pull_socket.recv(zmq.NOBLOCK)
                    except zmq.Again:
                        break
                decoded = self._decode_state(msgpack.unpackb(raw, raw=False))
                with self._state_lock:
                    self._streaming_state = decoded
            except zmq.Again:
                continue
            except Exception as e:
                if self._stream_running:
                    logger.warning("State stream decode error: %s", e)

    def _rpc_get_state(self) -> dict:
        """Fetch state synchronously via the command channel."""
        resp = self._send_command("get_state")
        if not resp.get("success"):
            raise RuntimeError(f"Failed to get state: {resp.get('error')}")

        state = self._decode_state(resp.get("state", {}))
        self._cached_state = state
        return state

    def _force_refresh_state(self) -> None:
        """Synchronously refresh the local cache after blocking ops."""
        state = self._rpc_get_state()
        with self._state_lock:
            self._streaming_state = state

    # ── API (mirrors FrankaRemoteController) ─────────────────────

    def connect(
        self,
        controller_type: str = "pid",
        timeout: float = None,
    ) -> bool:
        """Connect to robot via RobotServer.

        The server creates FrankaRemoteController using its own FCI IP config.
        This command starts the control loop and switches controller type.

        Args:
            controller_type: Initial controller (pid/osc/impedance/torque).
            timeout: Timeout in seconds.

        Returns True if successful.
        """
        if timeout is None:
            timeout = self.timeout
        resp = self._send_command("connect", {
            "controller_type": controller_type,
        })
        if not resp.get("success"):
            logger.error("Connect rejected: %s", resp.get("error"))
            return False
        result = self._wait_until_idle(timeout)
        if not result.get("success"):
            logger.error("Connect failed: %s", result.get("error"))
            return False
        self._force_refresh_state()
        return True

    def start(self, timeout: float = None) -> bool:
        """Start the control loop. Blocking.

        Returns True if successful.
        """
        if timeout is None:
            timeout = self.timeout
        resp = self._send_command("start")
        if not resp.get("success"):
            logger.error("Start rejected: %s", resp.get("error"))
            return False
        result = self._wait_until_idle(timeout)
        if not result.get("success", False):
            return False
        self._force_refresh_state()
        return True

    def stop(self) -> bool:
        """Stop the control loop.

        Returns True if successful.
        """
        resp = self._send_command("stop")
        return resp.get("success", False)

    def switch(self, controller_type: str) -> bool:
        """Switch controller type (pid/osc/impedance/torque).

        Returns True if successful.
        """
        resp = self._send_command("switch", {"type": controller_type})
        return resp.get("success", False)

    def set(self, attr: str, value: np.ndarray) -> bool:
        """Set a target attribute on the controller.

        Args:
            attr: Attribute name (e.g. "q_desired", "ee_desired", "torque").
            value: Target value as numpy array.

        Returns True if successful.
        """
        msg = {
            "command": "set",
            "params": {
                "attr": attr,
                "value": value.astype(np.float64).tobytes(),
                "shape": list(value.shape),
            },
        }
        try:
            packed = msgpack.packb(msg, use_bin_type=True)
            self._socket.send_multipart([b"", packed])
            return True
        except Exception:
            logger.exception("Failed to stream robot set command")
            return False

    def move(self, qpos: np.ndarray, timeout: float = None) -> bool:
        """Ruckig trajectory move to target joint position. Blocking.

        Args:
            qpos: Target joint angles [rad], shape (7,).
            timeout: Timeout in seconds.

        Returns True if successful.
        """
        if timeout is None:
            timeout = MOVE_TIMEOUT
        resp = self._send_command("move", {
            "qpos": qpos.astype(np.float64).tobytes(),
        })
        if not resp.get("success"):
            logger.error("Move rejected: %s", resp.get("error"))
            return False
        result = self._wait_until_idle(timeout)
        if not result.get("success", False):
            return False
        self._force_refresh_state()
        return True

    @property
    def state(self) -> dict:
        """Get current robot state (from server cache).

        Returns dict with numpy arrays: qpos, qvel, ee, jac, mm,
        last_torque, q_desired, timestamp.
        """
        with self._state_lock:
            if self._streaming_state is not None:
                self._cached_state = self._streaming_state
                return dict(self._streaming_state)
        return self._rpc_get_state()

    @property
    def running(self) -> bool:
        """Check if the controller is running."""
        resp = self._send_command("is_running")
        return resp.get("running", False)

    def disconnect(self) -> bool:
        """Tell server to release controller and clean up.

        Returns True if server acknowledged.
        """
        resp = self._send_command("disconnect")
        return resp.get("success", False)

    # ── Cleanup ──────────────────────────────────────────────────

    def close(self) -> None:
        """Disconnect from server and close ZMQ connection."""
        self._stream_running = False
        if self._state_thread.is_alive():
            self._state_thread.join(timeout=2.0)
        if self._pull_socket:
            self._pull_socket.close()
        if self._socket:
            try:
                self.disconnect()
            except Exception:
                pass
            self._socket.close()
        if self._ctx:
            self._ctx.term()
        logger.info("Robot client disconnected.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
