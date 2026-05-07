"""Data collector for LeRobot v3.0 format.

Pure data recorder - does not control robot or cameras.
Caller is responsible for robot control and image capture.
"""

import json
import logging
from pathlib import Path

import numpy as np
from lerobot.datasets import LeRobotDataset
from lerobot.datasets.feature_utils import DEFAULT_FEATURES

from franka_control.data.config import CollectionConfig
from franka_control.data.features import build_franka_features

logger = logging.getLogger(__name__)


class DataCollector:
    """Pure data recorder for LeRobot v3.0 format.

    Does NOT control robot or cameras - only records data.
    Caller is responsible for:
    - Creating and managing FrankaEnv, CameraManager
    - Controlling the robot (step/move_to/etc.)
    - Capturing images
    - Calling record_frame() at desired frequency

    Args:
        config: Collection configuration.
        resume: If True, resume existing dataset instead of creating new.
    """

    def __init__(self, config: CollectionConfig, resume: bool = False,
                 extra_features: dict | None = None):
        self.config = config

        features = build_franka_features(config, extra_features=extra_features)
        if resume:
            self.dataset = LeRobotDataset.resume(
                repo_id=config.repo_id,
                root=str(config.root),
                streaming_encoding=config.streaming_encoding,
                encoder_threads=config.encoder_threads,
                encoder_queue_maxsize=config.encoder_queue_maxsize,
            )
            # Validate features match
            default_features = set(DEFAULT_FEATURES.keys())
            existing_features = set(self.dataset.features.keys()) - default_features
            expected_features = set(features.keys())
            if existing_features != expected_features:
                raise ValueError(
                    f"Feature mismatch. Existing: {existing_features}, "
                    f"Expected: {expected_features}"
                )
        else:
            try:
                self.dataset = LeRobotDataset.create(
                    repo_id=config.repo_id,
                    root=str(config.root),
                    fps=config.fps,
                    features=features,
                    robot_type=config.robot_type,
                    use_videos=config.use_videos,
                    streaming_encoding=config.streaming_encoding,
                    encoder_threads=config.encoder_threads,
                    encoder_queue_maxsize=config.encoder_queue_maxsize,
                )
            except FileExistsError:
                raise FileExistsError(
                    f"Dataset directory already exists: {config.root}\n"
                    f"  To append episodes, add --resume\n"
                    f"  To start fresh, delete it first: rm -rf {config.root}"
                )

        self._episode_active = False
        self._current_instruction = None
        logger.info("DataCollector ready. Dataset: %s", config.repo_id)

    def start_episode(self, instruction: str = ""):
        """Start new episode.

        Args:
            instruction: Natural language task description.
        """
        if self._episode_active:
            raise RuntimeError("Episode already active")
        self._current_instruction = instruction or self.config.task_name
        self._episode_active = True
        logger.info("Episode started: %s", self._current_instruction)

    def record_frame(
        self,
        obs: dict,
        action: np.ndarray,
        images: dict[str, np.ndarray] | None = None,
        extra: dict | None = None,
    ) -> None:
        """Record one frame.

        Args:
            obs: Observation dict from FrankaEnv.get_observation().
            action: Applied action (after clipping).
            images: Camera images {cam_name: rgb_array (H,W,3) uint8}.
            extra: Optional project-specific fields to merge into the frame
                (caller must ensure the keys are registered in features), such
                as depth maps or task-specific annotations.
        """
        if not self._episode_active:
            raise RuntimeError("No active episode")

        # Validate action shape
        expected_dim = (
            8 if self.config.control_mode in ("joint_abs", "joint_delta") else 7
        )
        if action.shape != (expected_dim,):
            raise ValueError(
                f"Expected action shape ({expected_dim},), got {action.shape}"
            )

        # Build frame
        frame = {
            "observation.state": self._build_state(obs),
            "observation.joint_vel": obs["joint_vel"].astype(np.float32),
            "observation.ee_pose": np.concatenate([
                obs["ee_pos"], obs["ee_quat"]
            ]).astype(np.float32),
            "observation.effort": obs["joint_torque"].astype(np.float32),
            "action": action.astype(np.float32),
            "task": self._current_instruction,
        }

        # Add camera images
        if images:
            for cam_name, rgb in images.items():
                key = f"observation.images.{cam_name}"
                if key in self.dataset.features:
                    frame[key] = rgb

        if extra:
            frame.update(extra)

        self.dataset.add_frame(frame)

    def end_episode(self, success: bool = True):
        """End current episode and save.

        Args:
            success: Whether the episode was successful.
        """
        if not self._episode_active:
            raise RuntimeError("No active episode")

        if success or self.config.save_failure:
            ep_idx = self.dataset.meta.total_episodes
            self.dataset.save_episode()
            self._save_annotation(ep_idx, success)
            logger.info("Episode %d saved (success=%s)", ep_idx, success)
        else:
            self.dataset.clear_episode_buffer(delete_images=True)
            logger.info("Episode discarded (failure, save_failure=False)")

        self._episode_active = False

    def discard_episode(self):
        """Discard current episode without saving."""
        if self._episode_active:
            self.dataset.clear_episode_buffer(delete_images=True)
            self._episode_active = False
            logger.info("Episode discarded")

    def finalize(self):
        """Finalize dataset. Must be called when done recording."""
        if self._episode_active:
            raise RuntimeError("Cannot finalize with active episode")
        self.dataset.finalize()
        logger.info("Dataset finalized")

    def _build_state(self, obs: dict) -> np.ndarray:
        """Build observation.state vector from FrankaEnv observation."""
        parts = [obs["joint_pos"]]  # (7,)
        if "gripper_width" in obs:
            parts.append(obs["gripper_width"])  # (1,)
        else:
            parts.append(np.zeros(1, dtype=np.float32))
        return np.concatenate(parts).astype(np.float32)

    def _save_annotation(self, episode_idx: int, success: bool):
        """Save episode success annotation to meta/episode_annotations.json."""
        ann_path = self.config.root / "meta" / "episode_annotations.json"
        ann_path.parent.mkdir(parents=True, exist_ok=True)

        annotations = {}
        if ann_path.exists():
            annotations = json.loads(ann_path.read_text())

        annotations[str(episode_idx)] = {"success": success}
        ann_path.write_text(json.dumps(annotations, indent=2))
