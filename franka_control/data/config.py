"""Data collection configuration."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal


@dataclass
class CameraConfig:
    """Single camera configuration."""
    name: str
    serial: str
    width: int = 640
    height: int = 480
    fps: int = 60
    depth: bool = False


@dataclass
class CollectionConfig:
    """Data collection configuration for LeRobot v3.0 format."""

    # Dataset basics
    repo_id: str
    root: Path
    task_name: str

    # Robot connection
    robot_ip: str
    gripper_host: str
    gripper_port: int = 5556

    # Control mode
    control_mode: Literal["joint_abs", "joint_delta", "ee_abs", "ee_delta"] = "joint_abs"
    gripper_mode: Literal["binary", "continuous"] = "binary"

    # Recording parameters
    fps: int = 60
    cameras: list[CameraConfig] = field(default_factory=list)
    save_failure: bool = False

    # LeRobot parameters
    robot_type: str = "franka_fr3"
    use_videos: bool = True
    streaming_encoding: bool = True
    encoder_threads: int | None = None
    encoder_queue_maxsize: int = 30
