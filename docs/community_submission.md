# Franka Community Submission

This page keeps the submission material in the repository so it can be reviewed
before sending.

## Proposed Categories

- Robot Control & Motion Planning.
- Learning Environments and Datasets.

## Short Description

Franka Control is an all-in-one, no-ROS Python stack for Franka Research 3
control, teleoperation, motion planning, IK, RealSense integration, and LeRobot
data collection. It uses a dual-machine architecture with ZMQ-based robot and
gripper services, provides a Gymnasium-compatible environment for policies, and
includes tools for SpaceMouse and keyboard teleoperation, waypoint capture,
trajectory execution, synchronized multi-camera demonstration collection, and
dataset playback and analysis.

## Repository Links

| Item | URL |
|---|---|
| Repository | `https://github.com/ArrebolBlack/franka-control` |
| Release | `TBD after v0.1.0 release` |
| Demo media | `TBD after screenshots/GIFs are captured` |
| Hardware validation | `docs/hardware_validation.md` |

## Submission Email Draft

```text
Subject: Franka Community Contribution: Franka Control, a no-ROS Python stack for FR3 control and data collection

Dear Franka Community team,

I would like to submit an open-source project for consideration on the Franka
Community page:

Repository: https://github.com/ArrebolBlack/franka-control
Release: <insert release URL>
Demo: <insert demo video or GIF URL>

Franka Control is an all-in-one, no-ROS Python stack for Franka Research 3
control, teleoperation, motion planning, IK, RealSense integration, and LeRobot
data collection. It is designed for embodied AI, imitation learning,
reinforcement learning, and robotics/control research.

Key features:
- Dual-machine architecture separating the Franka FCI control PC from the
  algorithm/GPU machine.
- ZMQ robot and gripper services with high-frequency state streaming.
- Gymnasium-compatible FrankaEnv for policy and RL-style loops.
- Keyboard and SpaceMouse teleoperation.
- Waypoint capture and TOPPRA trajectory execution.
- RealSense multi-camera integration.
- LeRobot v3 dataset collection, playback, screenshot/video export, and
  trajectory/action analysis.

The project is not a ROS wrapper and does not replace franka_ros. It complements
the existing Franka ecosystem by providing a lightweight Python-native workflow
for learning-centric real-robot experiments.

Best regards,
<name>
```

## Send Only After

- `[ ]` CI is green on the public repository.
- `[ ]` `docs/hardware_validation.md` is filled with real tested values.
- `[ ]` README links to real demo media.
- `[ ]` `CHANGELOG.md` is finalized for `v0.1.0`.
- `[ ]` GitHub release `v0.1.0` exists.
