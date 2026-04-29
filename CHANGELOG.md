# Changelog

All notable user-facing changes will be documented in this file.

The format follows the spirit of Keep a Changelog, and this project uses
semantic versioning once public releases begin.

## [0.1.0] - Unreleased

### Added

- No-ROS dual-machine Franka Research 3 control stack.
- ZMQ robot and gripper services for separating the control PC from the
  algorithm/GPU PC.
- Gymnasium-compatible `FrankaEnv`.
- Keyboard and SpaceMouse teleoperation.
- Waypoint capture, route storage, and TOPPRA trajectory execution tools.
- Pinocchio-based FK/IK utilities.
- RealSense RGB camera integration.
- RealSense camera listing helper for filling `config/cameras.yaml`.
- LeRobot v3 dataset collection, resume, success/failure annotation, playback,
  screenshot export, video export, trajectory visualization, and action
  analysis.
- English README, Chinese README link, documentation index, quick start, API
  guide, data collection guide, ROS comparison, troubleshooting guide, and
  hardware validation matrix.
- Open-source project metadata: Apache-2.0 license, citation file,
  contributing guide, security policy, roadmap, issue templates, pull request
  template, and CI workflow.

### Changed

- Improved `collect_episodes` preview overlays and FPS reporting during live
  collection.
- Improved the dataset-exists error message to point users to `--resume` or a
  fresh dataset root.

### Known Limitations

- The project is not official Franka Robotics software.
- The project does not provide ROS TF, RViz, MoveIt, or ROS bag integration.
- Real robot use requires local safety review, conservative first motions, and
  operator supervision.
