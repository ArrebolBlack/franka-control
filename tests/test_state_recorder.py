"""Tests for state-stream conversion used during data collection."""

import time

import numpy as np

from franka_control.data.state_recorder import StateStreamRecorder, streaming_to_obs


def test_streaming_to_obs_shapes_and_quaternion_order():
    streaming_state = {
        "qpos": np.arange(7, dtype=np.float64),
        "qvel": np.ones(7, dtype=np.float64),
        "ee": np.eye(4, dtype=np.float64),
        "jac": np.ones((6, 7), dtype=np.float64),
        "last_torque": np.full(7, 0.5, dtype=np.float64),
    }

    obs = streaming_to_obs(streaming_state, gripper_width=0.04)

    assert obs["joint_pos"].shape == (7,)
    assert obs["joint_vel"].shape == (7,)
    assert obs["joint_torque"].shape == (7,)
    assert obs["ee_pos"].shape == (3,)
    assert obs["ee_quat"].shape == (4,)
    assert obs["ee_vel"].shape == (6,)
    assert obs["gripper_width"].shape == (1,)
    assert np.allclose(obs["ee_quat"], np.array([0.0, 0.0, 0.0, 1.0]))
    assert np.allclose(obs["ee_vel"], np.full(6, 7.0))
    assert obs["gripper_width"][0] == np.float32(0.04)


def test_state_stream_recorder_packages_rgb_and_depth_extra():
    class FakeRobot:
        @property
        def state(self):
            return {
                "qpos": np.arange(7, dtype=np.float64),
                "qvel": np.ones(7, dtype=np.float64),
                "ee": np.eye(4, dtype=np.float64),
                "jac": np.ones((6, 7), dtype=np.float64),
                "last_torque": np.full(7, 0.5, dtype=np.float64),
            }

    class FakeCameras:
        def read_latest(self):
            return {
                "wrist": {
                    "rgb": np.full((4, 5, 3), 7, dtype=np.uint8),
                    "depth": np.full((4, 5), 123, dtype=np.uint16),
                }
            }

    recorder = StateStreamRecorder(
        robot_client_fn=lambda: FakeRobot(),
        cameras=FakeCameras(),
        fps=20,
        buffer_seconds=1.0,
    )

    recorder.start()
    time.sleep(0.08)
    recorder.stop()
    frames = recorder.drain()

    assert frames
    obs, action, images, extra = frames[-1]
    assert action is None
    assert obs["joint_pos"].shape == (7,)
    assert images["wrist"].shape == (4, 5, 3)
    assert extra["observation.depths.wrist"].shape == (4, 5)
    assert extra["observation.depths.wrist"].dtype == np.uint16
    assert recorder.last_images["wrist"].shape == (4, 5, 3)
    assert recorder.last_extra["observation.depths.wrist"].shape == (4, 5)
