"""Tests for state-stream conversion used during data collection."""

import numpy as np

from franka_control.data.state_recorder import streaming_to_obs


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
