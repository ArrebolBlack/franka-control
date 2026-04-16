"""Franka Gripper ZMQ Client.

Runs on the algorithm machine. Communicates with GripperServer via ZMQ.

Usage:
    with GripperClient("172.16.0.2") as gripper:
        gripper.homing()
        gripper.open()
        gripper.grasp(width=0.02, force=40.0)
        state = gripper.get_state()
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import msgpack
import zmq

logger = logging.getLogger(__name__)

# Default timeout for blocking operations (seconds)
DEFAULT_TIMEOUT = 30.0


class GripperClient:
    """Client for remote Franka gripper control via ZMQ.

    Args:
        host: Gripper server host (control machine IP).
        port: ZMQ port.
        timeout: Default timeout for blocking operations in seconds.
    """

    def __init__(
        self,
        host: str,
        port: int = 5556,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout

        self._ctx = zmq.Context()
        self._socket = self._ctx.socket(zmq.DEALER)
        self._socket.setsockopt(zmq.RCVTIMEO, 5000)  # 5s recv timeout
        self._socket.setsockopt(zmq.SNDTIMEO, 5000)   # 5s send timeout
        self._socket.connect(f"tcp://{host}:{port}")
        logger.info("Connected to gripper server at %s:%d", host, port)

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
            logger.error("Timeout waiting for gripper server response")
            return {"success": False, "error": "Server timeout"}
        except Exception as e:
            logger.exception("Gripper command failed")
            return {"success": False, "error": str(e)}

    # ── Blocking API ─────────────────────────────────────────────

    def _wait_until_idle(self, timeout: float) -> dict:
        """Poll get_state until worker status becomes idle, then return
        the last worker result (the actual operation outcome)."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            resp = self._send_command("get_state")
            if not resp.get("success"):
                return resp
            state = resp.get("state", {})
            if state.get("status") == "idle":
                # Return the worker's actual operation result
                result = resp.get("result")
                if result is not None:
                    return result
                return {"success": True, "state": state}
            time.sleep(0.02)  # 50Hz polling
        return {"success": False, "error": "Timeout waiting for gripper"}

    def homing(self, timeout: float = None) -> bool:
        """Perform gripper homing (calibration).

        Returns True if successful.
        """
        if timeout is None:
            timeout = self.timeout
        resp = self._send_command("homing")
        if not resp.get("success"):
            logger.error("Homing rejected: %s", resp.get("error"))
            return False
        result = self._wait_until_idle(timeout)
        return result.get("success", False)

    def open(self, width: float = 0.08, speed: float = 0.1,
             timeout: float = None) -> bool:
        """Open gripper to specified width.

        Args:
            width: Target width in meters (default: 0.08).
            speed: Movement speed in m/s (default: 0.1).
            timeout: Timeout in seconds.

        Returns True if successful.
        """
        if timeout is None:
            timeout = self.timeout
        resp = self._send_command("open", {"width": width, "speed": speed})
        if not resp.get("success"):
            logger.error("Open rejected: %s", resp.get("error"))
            return False
        result = self._wait_until_idle(timeout)
        return result.get("success", False)

    def grasp(
        self,
        width: float = 0.02,
        speed: float = 0.1,
        force: float = 40.0,
        epsilon_inner: float = 0.005,
        epsilon_outer: float = 0.005,
        timeout: float = None,
    ) -> bool:
        """Grasp object at specified width with force control.

        Returns True if object grasped.
        """
        if timeout is None:
            timeout = self.timeout
        resp = self._send_command("grasp", {
            "width": width,
            "speed": speed,
            "force": force,
            "epsilon_inner": epsilon_inner,
            "epsilon_outer": epsilon_outer,
        })
        if not resp.get("success"):
            logger.error("Grasp rejected: %s", resp.get("error"))
            return False
        result = self._wait_until_idle(timeout)
        return result.get("success", False)

    def move(self, width: float, speed: float = 0.1) -> bool:
        """Move gripper to specified width (non-blocking, position only).

        Sends a pure position move command (no force control).
        Returns immediately without waiting for completion.
        If the gripper is busy, the command is rejected.

        Args:
            width: Target width in meters.
            speed: Movement speed in m/s (default: 0.1).

        Returns True if command was accepted.
        """
        resp = self._send_command("move", {
            "width": width,
            "speed": speed,
        })
        return resp.get("success", False)

    def stop(self) -> bool:
        """Stop current gripper motion.

        Returns True if successful.
        """
        resp = self._send_command("stop")
        return resp.get("success", False)

    def get_state(self) -> Optional[dict]:
        """Get current cached gripper state.

        Returns dict with: width, max_width, is_grasped, temperature, status.
        None if request failed.
        """
        resp = self._send_command("get_state")
        if resp.get("success"):
            return resp.get("state")
        return None

    def shutdown_server(self) -> bool:
        """Request server to shut down.

        Returns True if successful.
        """
        resp = self._send_command("shutdown")
        return resp.get("success", False)

    # ── Cleanup ──────────────────────────────────────────────────

    def close(self) -> None:
        """Close ZMQ connection."""
        if self._socket:
            self._socket.close()
        if self._ctx:
            self._ctx.term()
        logger.info("Gripper client disconnected.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
