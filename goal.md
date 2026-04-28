# Project Goal and Scope

This document defines the goal, boundary, and positioning for turning
`franka-control` into a classic open-source repository suitable for submission
to Franka Community.

## Primary Goal

Build `franka-control` into a trusted, well-documented, reproducible,
community-ready open-source project for Franka Research 3 users.

The intended public positioning is:

> Franka Control is an all-in-one, no-ROS Python stack for Franka Research 3
> control, teleoperation, motion planning, IK, RealSense integration, and
> LeRobot data collection.

## Submission Goal

Submit the project to Franka Community after the repository has:

- Clear English documentation.
- Real usage examples.
- Hardware validation records.
- CI and basic quality gates.
- Open-source project hygiene files.
- Demo media showing real workflows.
- A stable GitHub release.

## Current Execution Focus

As of 2026-04-28, the active focus is community-readiness polish before public
release:

- Missing docs, CI, GitHub issue templates, PR template, roadmap, and changelog
  have been added and committed locally.
- The new-user quick start has been expanded into offline, control-PC, and
  algorithm-PC paths.
- Remaining release blockers are real hardware validation, real demo media, CI
  confirmation on GitHub, and the `v0.1.0` GitHub release.

Target community categories:

- Robot Control & Motion Planning.
- Learning Environments and Datasets.

## Intended Users

Primary users:

- Researchers using Franka Research 3 for embodied AI.
- Imitation learning and reinforcement learning practitioners.
- Robotics/control researchers who want a lightweight Python workflow.
- Labs that do not want ROS as the primary runtime dependency.

Secondary users:

- Users who already have ROS stacks but want a Python-native data collection
  pipeline.
- Users who need teleoperation, waypoint collection, trajectory execution, and
  dataset review in one repository.

## Core Value Proposition

The repository should communicate these values clearly:

- No ROS runtime dependency.
- Dual-machine control architecture.
- Python-native API for learning and research.
- Fast state streaming over ZMQ.
- Gymnasium-compatible environment.
- Keyboard and SpaceMouse teleoperation.
- Waypoint capture and trajectory planning.
- Pinocchio FK/IK support.
- RealSense camera support.
- LeRobot v3 data collection and playback.

## Explicit Non-Goals

The project should not claim to be:

- An official Franka Robotics project.
- A replacement for `libfranka`.
- A replacement for `franka_ros`, MoveIt, RViz, or ROS-native workflows.
- A hard real-time controller on the algorithm/GPU machine.
- A full training framework for robot policies.
- A simulation benchmark.
- A safety-certified control system.

## Relationship to ROS

The project must consistently state:

- It does not require ROS runtime.
- It does not start ROS nodes.
- It does not depend on ROS topics, TF, launch files, or MoveIt.
- It complements ROS-based stacks rather than replacing them.
- Users should still choose ROS when they need MoveIt, RViz, TF trees, ROS bags,
  or integration with a larger ROS system.

## Safety Boundary

The project controls real robot hardware. All public documentation must make the
safety boundary explicit:

- Users are responsible for local robot safety.
- First tests should be low-speed and short-distance.
- Hardware-facing changes must document control modes, units, dimensions, and
  safety implications.
- Unsafe motion behavior is a critical bug.
- Silent state/action/image misalignment in datasets is a critical bug.

## Success Definition

The project succeeds when:

- A new FR3 user can understand the architecture from README alone.
- A new user can install and run the basic workflow using documented commands.
- A reviewer can see what hardware has been validated.
- CI verifies all non-hardware behavior.
- A release is available and citeable.
- Franka Community reviewers can quickly understand why this project is useful
  and distinct from existing ROS or low-level FCI projects.
