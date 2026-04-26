"""LeRobot feature schema builder for Franka robot."""

from franka_control.data.config import CollectionConfig


def build_franka_features(
    config: CollectionConfig,
    extra_features: dict | None = None,
) -> dict:
    """Build LeRobot v3.0 features dict for Franka robot.

    Args:
        config: Collection configuration.
        extra_features: Optional project-specific feature definitions to
            merge into the returned dict (e.g. ``observation.phase``).

    Returns:
        Features dict compatible with LeRobotDataset.create().
    """
    features = {}

    # observation.state: joint_pos(7) + gripper_width(1) = 8
    features["observation.state"] = {
        "dtype": "float32",
        "shape": (8,),
        "names": ["q0", "q1", "q2", "q3", "q4", "q5", "q6", "gripper_width"],
    }

    # observation.joint_vel: 7 DOF
    features["observation.joint_vel"] = {
        "dtype": "float32",
        "shape": (7,),
        "names": [f"dq{i}" for i in range(7)],
    }

    # observation.ee_pose: pos(3) + quat(4) in [qx, qy, qz, qw] order (SciPy)
    features["observation.ee_pose"] = {
        "dtype": "float32",
        "shape": (7,),
        "names": ["x", "y", "z", "qx", "qy", "qz", "qw"],
    }

    # observation.effort: joint torques
    features["observation.effort"] = {
        "dtype": "float32",
        "shape": (7,),
        "names": [f"tau{i}" for i in range(7)],
    }

    # action: dimension depends on control_mode
    if config.control_mode in ("joint_abs", "joint_delta"):
        action_dim = 8  # 7 joint + 1 gripper
        action_names = [f"q{i}" for i in range(7)] + ["gripper"]
    else:  # ee_abs, ee_delta
        action_dim = 7  # 6 (pos+rotvec) + 1 gripper
        action_names = ["x", "y", "z", "rx", "ry", "rz", "gripper"]

    features["action"] = {
        "dtype": "float32",
        "shape": (action_dim,),
        "names": action_names,
    }

    # cameras: (height, width, channels) format
    for cam in config.cameras:
        features[f"observation.images.{cam.name}"] = {
            "dtype": "video" if config.use_videos else "image",
            "shape": (cam.height, cam.width, 3),
            "names": ["height", "width", "channels"],
        }

    if extra_features:
        features.update(extra_features)

    return features
