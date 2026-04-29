# Changelog

All notable user-facing changes will be documented in this file.

The format follows the spirit of Keep a Changelog, and this project uses
semantic versioning.

## [0.1.0] - 2026-04-30

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
- Hardware validation record for a real Franka Research 3 setup with Franka
  Hand, D405/D435 RealSense cameras, keyboard teleoperation, SpaceMouse
  teleoperation, waypoint capture, trajectory execution, camera-backed
  collection, no-camera collection, dataset playback, and blocking-gripper
  collection validation.
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
- Clarified the README architecture description: robot command channel, state
  stream, gripper command channel, and `StateStreamRecorder` data path are now
  documented separately.

### Fixed

- Included bundled FR3v2 URDF and mesh assets in built source distributions and
  wheels so the default Pinocchio `IKSolver` can load its model after package
  installation.
- Ignored generated demo and test-output directories so local LeRobot metadata
  is not accidentally staged as release material.
- Redacted public validation documentation to avoid exposing lab-local IPs,
  hostnames, local paths, or camera serial numbers.

### Removed

- Removed the stale `franka_control.scripts.collect_data` entry point, which
  used an old `DataCollector` API. The supported collection command is
  `python -m franka_control.scripts.collect_episodes`.

### Known Limitations

- The project is not official Franka Robotics software.
- The project does not provide ROS TF, RViz, MoveIt, or ROS bag integration.
- Real robot use requires local safety review, conservative first motions, and
  operator supervision.
- `FrankaEnv` does not define task rewards or success termination logic.
- Hardware latency depends on the local network and control setup; the included
  validation record documents observed performance and should not be treated as a
  universal performance guarantee.
