# No-ROS Design and ROS Comparison

Franka Control intentionally avoids ROS as a runtime dependency. This is a design
choice for learning-centric robotics workflows, not a claim that ROS is unnecessary.

## Why Avoid ROS Runtime Here

Embodied AI experiments often need:

- A small Python API for policies and data pipelines.
- Simple deployment on an algorithm/GPU machine.
- Direct integration with Gymnasium, PyTorch, LeRobot, and custom training code.
- Fewer moving parts during teleoperation and dataset collection.
- Explicit control over what is recorded at each frame.

The project therefore uses:

- ZMQ RPC for robot and gripper commands.
- A dedicated state stream for high-frequency robot state.
- `FrankaEnv` as the main policy-facing API.
- LeRobot v3 as the dataset format.

## When ROS Is Still Better

Use ROS / MoveIt / `franka_ros` if you need:

- ROS-native perception and planning stacks.
- Existing ROS tooling, bags, TF trees, RViz, or MoveIt.
- Multi-robot systems already standardized on ROS messages.
- Integration with a larger ROS production stack.

## Relationship to Franka Lower Layers

This project still relies on Franka-compatible lower layers on the control PC:

| Layer | Used by this project |
|---|---|
| Franka FCI | required for real robot control |
| `aiofranka` | robot control backend behind `RobotServer` |
| `pylibfranka` | gripper backend behind `GripperServer` |
| `libfranka` | indirectly through the Python bindings |

The algorithm machine does not need those FCI libraries. It only talks to the
control machine over TCP.

## Design Tradeoffs

Benefits:

- Easy Python scripting.
- Clean separation between control PC and algorithm PC.
- Low-latency state streaming.
- Simple dataset capture for imitation learning and RL.
- Less setup overhead than a full ROS stack.

Costs:

- No built-in ROS TF tree, RViz, or MoveIt integration.
- No ROS bag format by default.
- You must manage your own safety wrappers, task termination, and reward logic.
- Hard real-time guarantees remain the responsibility of the FCI/control-machine side.

## Summary

Franka Control is best viewed as a Python-native research stack for Franka-based
embodied AI and control research. It complements ROS rather than replacing it.

## Practical Migration Guidance

| If you currently use... | Keep using it for... | Use Franka Control for... |
|---|---|---|
| `franka_ros` | ROS-native integration, TF/RViz/MoveIt workflows, ROS bags | Lightweight Python teleop, learning loops, and LeRobot data collection |
| `libfranka` directly | Custom C++ real-time controllers | Python-side research scripts and dataset tooling |
| LeRobot only | Training and dataset utilities | Real Franka data acquisition and synchronized robot/camera recording |

The intended boundary is clear: ROS is optional and external. Franka Control does
not start ROS nodes, publish ROS topics, consume TF, or require launch files.
