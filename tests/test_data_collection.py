"""Unit tests for data collection module."""

import tempfile
from pathlib import Path

import numpy as np
import pytest

from franka_control.data import (
    CameraConfig,
    CollectionConfig,
    build_franka_features,
)


class TestFeatureBuilder:
    """Test build_franka_features()."""

    def test_joint_mode_features(self):
        """Test feature schema for joint control modes."""
        config = CollectionConfig(
            repo_id="test/dataset",
            root=Path("/tmp/test"),
            task_name="test",
            robot_ip="127.0.0.1",
            gripper_host="127.0.0.1",
            control_mode="joint_abs",
        )
        features = build_franka_features(config)

        # Check action dimension
        assert features["action"]["shape"] == (8,)
        assert len(features["action"]["names"]) == 8
        assert features["action"]["names"][-1] == "gripper"

    def test_ee_mode_features(self):
        """Test feature schema for ee control modes."""
        config = CollectionConfig(
            repo_id="test/dataset",
            root=Path("/tmp/test"),
            task_name="test",
            robot_ip="127.0.0.1",
            gripper_host="127.0.0.1",
            control_mode="ee_delta",
        )
        features = build_franka_features(config)

        # Check action dimension
        assert features["action"]["shape"] == (7,)
        assert len(features["action"]["names"]) == 7
        assert features["action"]["names"][-1] == "gripper"

    def test_camera_features(self):
        """Test camera feature generation."""
        config = CollectionConfig(
            repo_id="test/dataset",
            root=Path("/tmp/test"),
            task_name="test",
            robot_ip="127.0.0.1",
            gripper_host="127.0.0.1",
            cameras=[
                CameraConfig(name="wrist", serial="xxx", width=640, height=480),
                CameraConfig(name="front", serial="yyy", width=1280, height=720),
            ],
        )
        features = build_franka_features(config)

        assert "observation.images.wrist" in features
        assert "observation.images.front" in features
        assert features["observation.images.wrist"]["shape"] == (480, 640, 3)
        assert features["observation.images.front"]["shape"] == (720, 1280, 3)


class TestCollectionConfig:
    """Test CollectionConfig validation."""

    def test_required_fields(self):
        """Test that required fields must be provided."""
        with pytest.raises(TypeError):
            CollectionConfig()

    def test_default_values(self):
        """Test default values are set correctly."""
        config = CollectionConfig(
            repo_id="test/dataset",
            root=Path("/tmp/test"),
            task_name="test",
            robot_ip="127.0.0.1",
            gripper_host="127.0.0.1",
        )
        assert config.control_mode == "joint_abs"
        assert config.gripper_mode == "binary"
        assert config.fps == 60
        assert config.save_failure is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


class TestDataCollector:
    """Test DataCollector lifecycle and validation."""

    @pytest.fixture
    def config(self, tmp_path):
        return CollectionConfig(
            repo_id="test/franka_test",
            root=tmp_path / "dataset",
            task_name="test_task",
            robot_ip="127.0.0.1",
            gripper_host="127.0.0.1",
            control_mode="joint_abs",
            use_videos=False,
            streaming_encoding=False,
        )

    @pytest.fixture
    def collector(self, config):
        from franka_control.data import DataCollector
        c = DataCollector(config)
        yield c
        if c._episode_active:
            c.discard_episode()
        c.finalize()

    def _make_obs(self):
        return {
            "joint_pos": np.zeros(7, dtype=np.float32),
            "joint_vel": np.zeros(7, dtype=np.float32),
            "joint_torque": np.zeros(7, dtype=np.float32),
            "ee_pos": np.zeros(3, dtype=np.float32),
            "ee_quat": np.array([0, 0, 0, 1], dtype=np.float32),
            "gripper_width": np.array([0.08], dtype=np.float32),
        }

    def test_episode_lifecycle(self, collector):
        """Test start -> record -> end episode."""
        collector.start_episode(instruction="pick cube")
        obs = self._make_obs()
        action = np.zeros(8, dtype=np.float32)
        collector.record_frame(obs, action)
        collector.end_episode(success=True)
        assert not collector._episode_active

    def test_double_start_raises(self, collector):
        """Test that starting an episode twice raises."""
        collector.start_episode()
        with pytest.raises(RuntimeError, match="already active"):
            collector.start_episode()

    def test_record_without_start_raises(self, collector):
        """Test that recording without starting raises."""
        obs = self._make_obs()
        action = np.zeros(8, dtype=np.float32)
        with pytest.raises(RuntimeError, match="No active episode"):
            collector.record_frame(obs, action)

    def test_wrong_action_shape_raises(self, collector):
        """Test that wrong action shape raises ValueError."""
        collector.start_episode()
        obs = self._make_obs()
        wrong_action = np.zeros(7, dtype=np.float32)  # should be 8 for joint_abs
        with pytest.raises(ValueError, match="Expected action shape"):
            collector.record_frame(obs, wrong_action)

    def test_discard_episode(self, collector):
        """Test discarding an episode."""
        collector.start_episode()
        obs = self._make_obs()
        action = np.zeros(8, dtype=np.float32)
        collector.record_frame(obs, action)
        collector.discard_episode()
        assert not collector._episode_active

    def test_finalize_with_active_episode_raises(self, collector):
        """Test that finalizing with active episode raises."""
        collector.start_episode()
        with pytest.raises(RuntimeError, match="Cannot finalize"):
            collector.finalize()

    def test_annotation_saved(self, collector, config):
        """Test that episode annotations are saved correctly."""
        collector.start_episode(instruction="test")
        obs = self._make_obs()
        action = np.zeros(8, dtype=np.float32)
        collector.record_frame(obs, action)
        collector.end_episode(success=True)

        ann_path = config.root / "meta" / "episode_annotations.json"
        assert ann_path.exists()
        import json
        annotations = json.loads(ann_path.read_text())
        assert "0" in annotations
        assert annotations["0"]["success"] is True

    def test_failure_discarded_by_default(self, collector, config):
        """Test that failed episodes are discarded when save_failure=False."""
        collector.start_episode()
        obs = self._make_obs()
        action = np.zeros(8, dtype=np.float32)
        collector.record_frame(obs, action)
        collector.end_episode(success=False)

        ann_path = config.root / "meta" / "episode_annotations.json"
        assert not ann_path.exists()

    def test_ee_mode_action_shape(self, tmp_path):
        """Test that ee mode expects 7D action."""
        from franka_control.data import DataCollector
        config = CollectionConfig(
            repo_id="test/franka_ee",
            root=tmp_path / "dataset_ee",
            task_name="test",
            robot_ip="127.0.0.1",
            gripper_host="127.0.0.1",
            control_mode="ee_delta",
            use_videos=False,
            streaming_encoding=False,
        )
        collector = DataCollector(config)
        collector.start_episode()
        obs = self._make_obs()

        # 7D should work
        action_7d = np.zeros(7, dtype=np.float32)
        collector.record_frame(obs, action_7d)

        # 8D should fail
        action_8d = np.zeros(8, dtype=np.float32)
        with pytest.raises(ValueError, match="Expected action shape"):
            collector.record_frame(obs, action_8d)

        collector.discard_episode()
        collector.finalize()
