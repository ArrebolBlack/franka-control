# Roadmap

This roadmap is intentionally conservative. The first goal is a trustworthy
real-robot data collection and control stack, not a broad robotics framework.

## v0.1: Community-Ready Baseline

- English README and documentation index.
- No-ROS dual-machine robot and gripper services.
- Gymnasium-compatible `FrankaEnv`.
- Keyboard and SpaceMouse teleoperation.
- Waypoint capture and TOPPRA trajectory execution.
- RealSense RGB capture and LeRobot v3 dataset writing.
- Dataset playback, screenshots, video export, trajectory plots, and action
  analysis.
- CI for tests, important script compilation, CLI help smoke tests, Markdown
  relative-link checks, and limited `ruff` checks.
- Hardware validation matrix and troubleshooting guide.

## v0.2: Safety and Validation Tooling

- Explicit workspace and velocity guardrails around common teleop paths.
- Safer default motion scales for first-run commands.
- Structured hardware validation scripts that emit machine-readable reports.
- Better latency and dropped-frame diagnostics.
- More tests around action clipping, state streaming, and gripper blocking
  behavior.

## v0.3: Dataset and Calibration Tools

- Stronger dataset integrity checks for frame/action/state alignment.
- Camera calibration helpers and clearer multi-camera setup docs.
- Dataset repair and migration utilities for schema changes.
- More visualization options for trajectories, gripper events, and camera
  synchronization.

## Future Directions

- Optional ROS bridge for users who need TF, RViz, MoveIt, or ROS bags.
- Simulation bridge examples for offline policy development.
- Hand-eye calibration workflow.
- Policy deployment examples that consume `FrankaEnv`.
- Expanded hardware matrix for different Franka system versions, cameras, and
  teleoperation devices.

## Non-Goals

- Replacing `franka_ros`, MoveIt, RViz, or `libfranka`.
- Claiming official Franka Robotics support.
- Providing a safety-certified controller.
- Becoming a full policy training framework.
