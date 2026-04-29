"""Offline tests for FrankaEnv action-space and clipping logic."""

import numpy as np
import pytest

from franka_control.envs.franka_env import (
    FrankaEnv,
    JOINT_LIMIT_HIGH,
    JOINT_LIMIT_LOW,
)


def test_invalid_action_mode_raises_before_hardware_connection():
    with pytest.raises(ValueError, match="action_mode"):
        FrankaEnv(robot_ip="127.0.0.1", action_mode="invalid")


def test_action_space_dimensions_with_and_without_gripper():
    env_no_gripper = FrankaEnv(
        robot_ip="127.0.0.1",
        gripper_host=None,
        action_mode="ee_delta",
    )
    assert env_no_gripper.action_space.shape == (6,)

    env_with_gripper = FrankaEnv(
        robot_ip="127.0.0.1",
        gripper_host="127.0.0.1",
        action_mode="joint_abs",
        gripper_mode="binary",
    )
    assert env_with_gripper.action_space.shape == (8,)
    assert env_with_gripper.action_space.low[-1] == 0.0
    assert env_with_gripper.action_space.high[-1] == 1.0


def test_joint_targets_clip_to_fr3_joint_limits():
    env = FrankaEnv(robot_ip="127.0.0.1", action_mode="joint_abs")

    high = env._clip_robot_target(np.full(7, 999.0))
    low = env._clip_robot_target(np.full(7, -999.0))

    assert np.allclose(high, JOINT_LIMIT_HIGH)
    assert np.allclose(low, JOINT_LIMIT_LOW)
