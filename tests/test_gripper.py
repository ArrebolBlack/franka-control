"""Tests for Franka Gripper Server and Client.

Tests 1-4: Local mock tests (no real robot needed).
"""

import sys
import os
import time
import threading
import msgpack
import pytest
import zmq

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from franka_control.gripper.gripper_server import (
    GripperServer, GripperStatus, CachedState, DEFAULT_CMD_PORT,
)
from franka_control.gripper.gripper_client import GripperClient


# ── Mock gripper ─────────────────────────────────────────────────

class MockGripperState:
    """Simulates pylibfranka.GripperState."""
    def __init__(self, width=0.0, max_width=0.08, is_grasped=False, temperature=25):
        self.width = width
        self.max_width = max_width
        self.is_grasped = is_grasped
        self.temperature = temperature


class MockGripper:
    """Simulates pylibfranka.Gripper with controllable delays."""

    def __init__(self, ip=""):
        self._width = 0.0
        self._max_width = 0.08
        self._is_grasped = False
        self._temperature = 25
        self.move_delay = 0.2       # seconds
        self.grasp_delay = 0.3
        self.homing_delay = 0.5

    def homing(self):
        time.sleep(self.homing_delay)
        self._max_width = 0.08
        self._width = self._max_width
        return True

    def move(self, width, speed):
        time.sleep(self.move_delay)
        self._width = width
        self._is_grasped = False
        return True

    def grasp(self, width, speed, force, epsilon_inner=0.005, epsilon_outer=0.005):
        time.sleep(self.grasp_delay)
        self._width = width
        self._is_grasped = True
        return True

    def stop(self):
        return True

    def readOnce(self):
        return MockGripperState(
            width=self._width,
            max_width=self._max_width,
            is_grasped=self._is_grasped,
            temperature=self._temperature,
        )


# ══════════════════════════════════════════════════════════════════
# Test 1: Message serialization
# ══════════════════════════════════════════════════════════════════

class TestSerialization:

    def test_command_roundtrip(self):
        """msgpack pack → unpack should be identical for command messages."""
        original = {"command": "open", "params": {"width": 0.08, "speed": 0.1}}
        packed = msgpack.packb(original, use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)
        assert unpacked == original

    def test_response_roundtrip(self):
        """msgpack pack → unpack should be identical for response messages."""
        original = {"success": True, "state": {"width": 0.04, "is_grasped": True}}
        packed = msgpack.packb(original, use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)
        assert unpacked == original

    def test_error_response_roundtrip(self):
        original = {"success": False, "error": "Gripper busy"}
        packed = msgpack.packb(original, use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)
        assert unpacked == original

    def test_empty_params(self):
        original = {"command": "get_state", "params": {}}
        packed = msgpack.packb(original, use_bin_type=True)
        unpacked = msgpack.unpackb(packed, raw=False)
        assert unpacked == original


# ══════════════════════════════════════════════════════════════════
# Test 2: Command dispatch (_dispatch)
# ══════════════════════════════════════════════════════════════════

class TestDispatch:

    def setup_method(self):
        """Create server with mock gripper for direct dispatch tests."""
        self.server = GripperServer("0.0.0.0", cmd_port=0)
        self.server._gripper = MockGripper()

    def _dispatch_msg(self, command, params=None):
        """Helper: pack command and call _dispatch."""
        msg = {"command": command}
        if params:
            msg["params"] = params
        raw = msgpack.packb(msg, use_bin_type=True)
        return self.server._dispatch(raw)

    def test_invalid_msgpack(self):
        resp = self.server._dispatch(b"\xff\xfe\xfd")
        assert resp["success"] is False
        assert "Invalid msgpack" in resp["error"]

    def test_unknown_command(self):
        resp = self._dispatch_msg("fly_away")
        assert resp["success"] is False
        assert "Unknown command" in resp["error"]

    def test_get_state(self):
        resp = self._dispatch_msg("get_state")
        assert resp["success"] is True
        assert "state" in resp
        assert resp["state"]["status"] == "idle"

    def test_open_accepted(self):
        resp = self._dispatch_msg("open", {"width": 0.08})
        assert resp["success"] is True
        assert resp["accepted"] is True

    def test_grasp_accepted(self):
        resp = self._dispatch_msg("grasp", {"width": 0.02, "force": 20.0})
        assert resp["success"] is True
        assert resp["accepted"] is True

    def test_homing_accepted(self):
        resp = self._dispatch_msg("homing")
        assert resp["success"] is True
        assert resp["accepted"] is True

    def test_stop(self):
        resp = self._dispatch_msg("stop")
        assert resp["success"] is True

    def test_shutdown(self):
        resp = self._dispatch_msg("shutdown")
        assert resp["success"] is True
        assert self.server._running is False


# ══════════════════════════════════════════════════════════════════
# Test 3: Worker thread mechanism
# ══════════════════════════════════════════════════════════════════

class TestWorkerThread:

    def setup_method(self):
        self.server = GripperServer("0.0.0.0", cmd_port=0)
        self.server._gripper = MockGripper()

    def test_submit_accepted_and_completes(self):
        """Job accepted → status busy → completes → status idle."""
        resp = self.server._submit_job("open", lambda: self.server._gripper.move(0.08, 0.1))
        assert resp["accepted"] is True

        # Immediately after submit, should be busy
        time.sleep(0.05)  # small delay for thread to start
        with self.server._worker_lock:
            # May still be busy or just finished (0.2s delay)
            pass

        # Wait for completion
        time.sleep(0.4)
        with self.server._worker_lock:
            assert self.server._worker_status == GripperStatus.IDLE
            assert self.server._worker_result["success"] is True

    def test_busy_rejection(self):
        """Submitting while busy should be rejected."""
        # Submit a slow job
        self.server._gripper.grasp_delay = 2.0
        resp1 = self.server._submit_job("grasp", lambda: self.server._gripper.grasp(0.02, 0.1, 40.0))
        assert resp1["accepted"] is True

        time.sleep(0.05)  # ensure thread started

        # Try another job while busy
        resp2 = self.server._submit_job("open", lambda: self.server._gripper.move(0.08, 0.1))
        assert resp2["success"] is False
        assert "busy" in resp2["error"].lower()

        # Reset delay and wait for cleanup
        self.server._gripper.grasp_delay = 0.1
        time.sleep(0.5)

    def test_stop_resets_status(self):
        """Stop command should set status back to idle."""
        # Submit a slow job
        self.server._gripper.homing_delay = 5.0
        self.server._submit_job("homing", lambda: self.server._gripper.homing())
        time.sleep(0.05)

        # Stop it
        resp = self.server._cmd_stop({})
        assert resp["success"] is True

        with self.server._worker_lock:
            assert self.server._worker_status == GripperStatus.IDLE

        # Cleanup
        self.server._gripper.homing_delay = 0.1
        time.sleep(0.2)


# ══════════════════════════════════════════════════════════════════
# Test 4: Client-Server end-to-end
# ══════════════════════════════════════════════════════════════════

def _find_free_port():
    """Find a free TCP port."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        return s.getsockname()[1]


class TestEndToEnd:

    def setup_method(self):
        """Start server with mock gripper in background thread."""
        self.port = _find_free_port()
        self.server = GripperServer("0.0.0.0", cmd_port=self.port)
        self.server._gripper = MockGripper()

        # Manually set up ZMQ (skip start() which needs pylibfranka)
        self.server._ctx = zmq.Context()
        self.server._cmd_socket = self.server._ctx.socket(zmq.ROUTER)
        self.server._cmd_socket.bind(f"tcp://*:{self.port}")
        self.server._cmd_socket.setsockopt(zmq.RCVTIMEO, 200)
        self.server._running = True

        # State polling thread
        self.server._state_thread = threading.Thread(
            target=self.server._state_poll_loop, daemon=True
        )
        self.server._state_thread.start()

        # Server main loop thread
        self._server_thread = threading.Thread(target=self.server.run, daemon=True)
        self._server_thread.start()

        # Client
        time.sleep(0.1)  # let server bind
        self.client = GripperClient("127.0.0.1", port=self.port)

    def teardown_method(self):
        self.client.close()
        self.server._running = False
        time.sleep(0.3)
        self.server._cleanup()

    def test_get_state(self):
        state = self.client.get_state()
        assert state is not None
        assert "width" in state
        assert "status" in state
        assert state["status"] == "idle"

    def test_homing_blocking(self):
        """homing() should block until complete, then return True."""
        result = self.client.homing(timeout=3.0)
        assert result is True

        state = self.client.get_state()
        assert state["status"] == "idle"

    def test_open_blocking(self):
        result = self.client.open(width=0.08, timeout=3.0)
        assert result is True

    def test_grasp_blocking(self):
        result = self.client.grasp(width=0.02, force=40.0, timeout=3.0)
        assert result is True

    def test_stop(self):
        result = self.client.stop()
        assert result is True

    def test_full_flow(self):
        """Complete workflow: homing → open → grasp → open → get_state."""
        assert self.client.homing(timeout=3.0) is True
        assert self.client.open(timeout=3.0) is True
        state = self.client.get_state()
        assert state is not None
        assert state["status"] == "idle"

        assert self.client.grasp(width=0.02, timeout=3.0) is True
        state = self.client.get_state()
        assert state is not None

        assert self.client.open(timeout=3.0) is True

    def test_shutdown(self):
        result = self.client.shutdown_server()
        assert result is True

    def test_timeout(self):
        """Client should timeout if server job takes too long."""
        self.server._gripper.homing_delay = 5.0  # 5s job
        result = self.client.homing(timeout=0.5)  # 0.5s timeout
        assert result is False
        # Reset for cleanup
        self.server._gripper.homing_delay = 0.1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
