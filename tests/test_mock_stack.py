"""Tests for the mock stack (MuJoCo sim server, sim hand, mock cameras, policy server).

All hardware-free. The robot-server tests need aiofranka + mujoco (franka
environment); the policy-server tests need openpi_client.
"""

import os
import socket
import sys
import threading
import time

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

pytest.importorskip("aiofranka", reason="mock robot server runs on aiofranka's MuJoCo sim")

from franka_control.gripper.gripper_client import GripperClient  # noqa: E402
from franka_control.mock.cameras import MockCameraManager  # noqa: E402
from franka_control.mock.gripper_server import MockGripperServer, SimHand  # noqa: E402
from franka_control.mock.robot_server import MockRobotServer  # noqa: E402
from franka_control.mock.sim_controller import SimControllerAdapter  # noqa: E402
from franka_control.robot.robot_client import RobotClient  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────


def _find_free_port() -> int:
    with socket.socket() as s:
        s.bind(("", 0))
        return s.getsockname()[1]


def _wait_for_port(port: int, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                return
        except OSError:
            time.sleep(0.02)
    raise TimeoutError(f"port {port} did not open")


def _wait_until(predicate, timeout: float = 4.0, interval: float = 0.02) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False


# ── Sim controller adapter ───────────────────────────────────────


class TestSimControllerAdapter:
    def setup_method(self):
        self.ctrl = SimControllerAdapter()
        self.ctrl.start()

    def teardown_method(self):
        self.ctrl.stop()

    def test_state_layout(self):
        state = self.ctrl.state
        shapes = {
            "qpos": (7,), "qvel": (7,), "ee": (4, 4), "jac": (6, 7),
            "mm": (7, 7), "last_torque": (7,), "q_desired": (7,),
        }
        for key, shape in shapes.items():
            assert state[key].shape == shape, f"state['{key}']"
        assert isinstance(state["timestamp"], float) and state["timestamp"] > 0

    def test_pid_tracking(self):
        self.ctrl.switch("pid")
        target = np.array(self.ctrl.state["qpos"]) + np.array([0.2, 0, 0, 0, 0, 0, 0])
        self.ctrl.set("q_desired", target)
        assert _wait_until(
            lambda: np.abs(self.ctrl.state["qpos"] - target).max() < 0.05
        ), "PID did not track q_desired"

    def test_osc_tracking(self):
        self.ctrl.switch("osc")
        target_ee = self.ctrl.state["ee"].copy()
        target_ee[2, 3] += 0.03
        self.ctrl.set("ee_desired", target_ee)
        assert _wait_until(
            lambda: abs(self.ctrl.state["ee"][2, 3] - target_ee[2, 3]) < 0.01
        ), "OSC did not track ee_desired"

    def test_move_abort_returns_promptly(self):
        # The invariant RobotServer relies on: a move() blocked in another
        # thread must return quickly when stop() fires, or the server kills
        # itself after a 5 s join timeout (robot_server._handle_stop).
        self.ctrl.switch("pid")
        target = np.array([0.6, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])
        returned = threading.Event()

        def run():
            self.ctrl.move(target)
            returned.set()

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        time.sleep(0.3)

        stop_t0 = time.monotonic()
        self.ctrl.stop()
        assert returned.wait(timeout=2.0), "move() did not return after stop()"
        assert time.monotonic() - stop_t0 < 1.0
        assert self.ctrl.running is False

    def test_restart_after_abort(self):
        self.ctrl.switch("pid")
        far = np.array([0.6, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])
        thread = threading.Thread(target=lambda: self.ctrl.move(far), daemon=True)
        thread.start()
        time.sleep(0.3)
        self.ctrl.stop()
        thread.join(timeout=2.0)
        assert not thread.is_alive()

        # The server reuses the adapter after a stop: start + move again.
        self.ctrl.start()
        assert self.ctrl.running
        near = np.array(self.ctrl.state["qpos"]) + np.array([0.05, 0, 0, 0, 0, 0, 0])
        self.ctrl.move(near)
        assert np.abs(self.ctrl.state["qpos"] - near).max() < 0.05


# ── Mock robot server protocol ───────────────────────────────────


class TestMockRobotServerProtocol:
    def setup_method(self):
        self.cmd_port = _find_free_port()
        self.state_port = _find_free_port()
        self.server = MockRobotServer(
            fci_ip="sim",
            cmd_port=self.cmd_port,
            state_poll_hz=100.0,
            state_stream_port=self.state_port,
        )
        self.thread = threading.Thread(
            target=self.server.run, daemon=True, name="mock-robot-server"
        )
        self.thread.start()
        _wait_for_port(self.cmd_port)

    def teardown_method(self):
        self.server._running = False
        self.thread.join(timeout=5.0)

    def _client(self) -> RobotClient:
        return RobotClient(
            host="127.0.0.1", port=self.cmd_port, state_stream_port=self.state_port
        )

    def test_connect_set_state(self):
        client = self._client()
        try:
            assert client.connect(controller_type="pid")
            assert client.running is True
            qpos = client.state["qpos"]
            assert qpos.shape == (7,)

            target = qpos + np.array([0.15, 0, 0, 0, 0, 0, 0])
            assert client.set("q_desired", target.astype(np.float64))
            assert _wait_until(
                lambda: np.abs(client.state["qpos"] - target).max() < 0.06
            ), "qpos did not converge to the streaming target"
        finally:
            client.disconnect()
            client.close()

    def test_stop_during_move_does_not_kill_server(self):
        client = self._client()
        try:
            assert client.connect(controller_type="pid")
            far = client.state["qpos"] + np.array([0.5, 0, 0, 0, 0, 0, 0])

            moved = threading.Thread(
                target=lambda: client.move(far.astype(np.float64)), daemon=True
            )
            moved.start()
            time.sleep(0.4)
            assert client.stop()
            moved.join(timeout=6.0)
            assert not moved.is_alive(), "client.move() never returned after stop"

            # The invariant that matters: the mock server survived.
            assert self.thread.is_alive(), "mock server shut itself down"
            assert client.running is False
            assert client.start() is True
            assert client.running is True
        finally:
            client.disconnect()
            client.close()


# ── Sim hand (unit) ──────────────────────────────────────────────


class TestSimHand:
    def test_grasp_without_object(self):
        hand = SimHand()
        hand.homing()
        assert hand.read_once().width == pytest.approx(0.08, abs=1e-6)
        assert hand.grasp(0.0, 0.1, 40.0) is True
        state = hand.read_once()
        assert state.width == pytest.approx(0.0, abs=1e-6)
        assert state.is_grasped is False

    def test_grasp_blocked_by_object(self):
        hand = SimHand(object_width=0.03)
        hand.homing()
        assert hand.grasp(0.0, 0.1, 40.0) is False
        state = hand.read_once()
        assert state.width == pytest.approx(0.03, abs=1e-6)
        assert state.is_grasped is True

    def test_stop_unblocks_motion(self):
        hand = SimHand()
        hand.homing()
        thread = threading.Thread(target=lambda: hand.move(0.0, 0.05), daemon=True)
        thread.start()  # a full close at 0.05 m/s takes ~1.6 s
        time.sleep(0.2)
        hand.stop()
        thread.join(timeout=1.0)
        assert not thread.is_alive()
        assert 0.0 < hand.read_once().width < 0.08  # stopped mid-stroke


# ── Mock gripper server protocol ─────────────────────────────────


class TestMockGripperServerProtocol:
    def setup_method(self):
        self.port = _find_free_port()
        self.server = MockGripperServer("sim", cmd_port=self.port, state_poll_hz=50.0)
        self.server.start()
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()
        _wait_for_port(self.port)

    def teardown_method(self):
        self.server._running = False
        self.thread.join(timeout=5.0)

    def test_homing_open_grasp(self):
        # get_state() reads the server's polled cache (~20 Hz), which lags a
        # finished motion by up to one poll period — same as the real stack —
        # so poll until the reported width settles instead of asserting once.
        client = GripperClient("127.0.0.1", self.port)

        def width_settles(target):
            return lambda: abs(client.get_state()["width"] - target) < 2e-3

        try:
            assert client.homing()
            assert _wait_until(width_settles(0.08), timeout=2.0), "homing width"
            assert client.open()
            assert _wait_until(width_settles(0.08), timeout=2.0), "open width"
            assert client.grasp(width=0.0, speed=0.1, force=40.0)
            assert _wait_until(width_settles(0.0), timeout=2.0), "grasp width"
            assert client.get_state()["is_grasped"] is False
        finally:
            client.close()


# ── Mock cameras ─────────────────────────────────────────────────


class TestMockCameras:
    def test_synthetic_frames(self):
        cameras = MockCameraManager(
            {"front": "synthetic", "wrist": "synthetic"}, resolution=(64, 48)
        )
        frames = cameras.read_latest()
        assert set(frames) == {"front", "wrist"}
        rgb = frames["front"]["rgb"]
        assert rgb.shape == (48, 64, 3)
        assert rgb.dtype == np.uint8
        assert cameras.camera_names == ["front", "wrist"]

    def test_dir_source_cycles(self, tmp_path):
        cv2 = pytest.importorskip("cv2")
        for i in range(3):
            img = np.full((24, 32, 3), i * 80, dtype=np.uint8)
            cv2.imwrite(str(tmp_path / f"frame_{i}.png"), img)
        cameras = MockCameraManager.from_spec(
            f"front=dir:{tmp_path}", resolution=(32, 24)
        )
        frame = cameras.read_latest()["front"]["rgb"]
        assert frame.shape == (24, 32, 3)
        seen = {
            int(cameras.read_latest()["front"]["rgb"][0, 0, 0]) for _ in range(3)
        }
        assert len(seen) >= 2, "directory frames should cycle"

    def test_bad_source_raises(self):
        with pytest.raises(ValueError):
            MockCameraManager({"front": "webcam"})
        with pytest.raises(ValueError):
            MockCameraManager.from_spec("front=")


# ── Client shutdown with no server ───────────────────────────────


class TestClientShutdownWithoutServer:
    """Closing a client whose server never existed must not hang (ZMQ linger)."""

    def test_robot_client_close_without_server(self):
        client = RobotClient(
            host="127.0.0.1", port=_find_free_port(), state_stream_port=_find_free_port()
        )
        assert client.connect(timeout=1.0) is False  # ~5 s recv timeout
        done = threading.Event()

        def _close():
            client.close()
            done.set()

        threading.Thread(target=_close, daemon=True).start()
        assert done.wait(timeout=15.0), "RobotClient.close() hung (ZMQ linger)"

    def test_gripper_client_close_without_server(self):
        client = GripperClient("127.0.0.1", _find_free_port())
        started = time.monotonic()
        client.close()
        assert time.monotonic() - started < 2.0


# ── Mock policy server (openpi protocol) ─────────────────────────


class TestMockPolicyServer:
    def _start_server(self, **kwargs) -> int:
        from franka_control.mock.policy_server import MockPolicy, MockPolicyServer

        port = _find_free_port()
        server = MockPolicyServer(
            MockPolicy(action_dim=7, horizon=16),
            host="127.0.0.1",
            port=port,
            metadata={"policy": "test", "action_dim": 7, "action_horizon": 16},
            **kwargs,
        )
        threading.Thread(target=server.serve_forever, daemon=True).start()
        _wait_for_port(port)
        return port

    def test_roundtrip_with_openpi_client(self):
        pytest.importorskip("openpi_client")
        from openpi_client import websocket_client_policy

        port = self._start_server()
        client = websocket_client_policy.WebsocketClientPolicy(
            host="127.0.0.1", port=port
        )
        assert client.get_server_metadata()["action_dim"] == 7

        obs = {
            "observation/state": np.zeros(8, dtype=np.float32),
            "observation/image": np.zeros((224, 224, 3), dtype=np.uint8),
            "observation/wrist_image": np.zeros((224, 224, 3), dtype=np.uint8),
            "prompt": "test",
        }
        result = client.infer(obs)
        assert result["actions"].shape == (16, 7)
        assert result["server_timing"]["infer_ms"] >= 0

    def test_error_frame_raises_on_client(self):
        pytest.importorskip("openpi_client")
        from openpi_client import websocket_client_policy

        port = self._start_server(fail_every=1)
        client = websocket_client_policy.WebsocketClientPolicy(
            host="127.0.0.1", port=port
        )
        with pytest.raises(RuntimeError, match="mock failure injection"):
            client.infer({"observation/state": np.zeros(8, np.float32), "prompt": "x"})
