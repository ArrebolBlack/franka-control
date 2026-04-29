# Franka Community Readiness Plan

This plan turns `franka-control` from a capable research codebase into a
polished open-source project that can credibly be submitted to Franka Community.

The target is not only "more features". The target is a repository that a new
Franka Research 3 user can understand, install, run, verify, and trust.

## Current Status

As of 2026-04-29:

- Phase 1 documentation foundation is complete.
- Phase 2 quick-start expansion is complete locally.
- Phase 3 troubleshooting and hardware validation docs are complete locally;
  real setup values and core FR3 workflow results are recorded, with one
  blocking-gripper camera-frame continuity check still pending.
- Phase 4 CI and quality gates are configured locally.
- Phase 5 open-source hygiene files are complete locally.
- Phase 6 demo media is partially complete: the architecture diagram exists,
  while real workflow screenshots/GIFs are still pending.
- Community-readiness implementation is committed locally as `f988044`.
- GitHub Actions is green on `origin/main` after fixing ignored local-file links
  in `docs/README.md`.
- GitHub Actions v6 upgrade is complete; run `25049362136` passed after the
  workflow moved to `actions/checkout@v6` and `actions/setup-python@v6`.
- GitHub About description, topics, required labels, `v0.1.0` milestone, and
  release-blocker issues are configured.
- Hardware validation helper script is added to reduce manual setup reporting.
- GitHub Actions run `25071752853` passed after adding validation helper
  coverage.
- Media capture runbook exists for the remaining real workflow screenshots/GIFs.
- Release materials checklist exists to guide collection of hardware details,
  validation evidence, media files, demo links, and submission inputs.
- Initial real setup/environment values are recorded in
  `docs/hardware_validation.md`.
- Core hardware workflow results are recorded; blocking-gripper camera-frame
  validation and real workflow screenshots/GIFs are still pending.
- Phase 7 release and Phase 8 Franka Community submission are blocked until
  hardware validation, demo media, and GitHub release steps are complete.

## 1. Project Positioning

### Core Positioning

Use this positioning consistently in GitHub About, README, release notes, and
Franka Community submission material:

> Franka Control is an all-in-one, no-ROS Python stack for Franka Research 3
> control, teleoperation, motion planning, IK, RealSense integration, and
> LeRobot data collection.

### Why This Positioning Works

- It clearly differentiates the project from `franka_ros`, which is ROS-native.
- It clearly differentiates the project from `libfranka`, which is a lower-level
  C++ FCI library.
- It clearly differentiates the project from learning-only stacks by emphasizing
  the full workflow: control, teleoperation, trajectory planning, cameras, and
  dataset collection.
- It maps naturally to Franka Community categories:
  - Robot Control & Motion Planning
  - Learning Environments and Datasets

### GitHub About

Recommended GitHub About text:

```text
No-ROS Python stack for Franka Research 3 control, teleoperation, trajectory planning, IK, RealSense, and LeRobot data collection.
```

Recommended GitHub topics:

```text
franka
franka-research-3
robot-control
robotics
teleoperation
motion-planning
inverse-kinematics
gymnasium
realsense
lerobot
imitation-learning
reinforcement-learning
no-ros
```

## 2. Current Strengths to Preserve

Do not dilute these strengths while polishing the repository:

- No ROS runtime dependency.
- Dual-machine architecture:
  - Control PC runs robot and gripper services.
  - Algorithm/GPU PC runs teleop, learning scripts, cameras, and data collection.
- High-frequency ZMQ state stream.
- Gymnasium-compatible `FrankaEnv`.
- SpaceMouse and keyboard teleoperation.
- Waypoint capture and TOPPRA trajectory execution.
- Pinocchio-based FK/IK utilities.
- Multi-RealSense camera support.
- LeRobot v3 dataset collection, resume, annotation, playback, screenshot, video
  export, trajectory visualization, and action analysis.

## 3. Definition of Done

The repository is ready for Franka Community submission when all items below are
complete.

### Documentation

- English README is the default GitHub entry point.
- Chinese README is retained and linked from the English README.
- README has a clear no-ROS positioning and explains the relationship to ROS,
  `franka_ros`, `libfranka`, `aiofranka`, `pylibfranka`, and LeRobot.
- New users can follow a complete install and quick-start path without reading
  source code.
- All CLI examples match actual `--help` output.
- Hardware-specific assumptions are explicit.

### Media

- README includes or links to:
  - System architecture diagram.
  - Teleoperation GIF or screenshot.
  - Data collection preview GIF or screenshot.
  - Dataset player screenshot.
  - Trajectory/action analysis screenshot.

### Engineering Quality

- CI runs on GitHub Actions.
- Unit tests pass in CI.
- CLI scripts at least pass `--help` smoke tests in CI.
- Markdown relative links are checked.
- `ruff` or equivalent linting is configured.
- No hardware is required for CI.

### Release Readiness

- `LICENSE` exists.
- `CITATION.cff` exists.
- `CONTRIBUTING.md` exists.
- `SECURITY.md` exists.
- `CHANGELOG.md` exists.
- `ROADMAP.md` exists.
- GitHub issue templates exist.
- First GitHub release exists: `v0.1.0`.
- Hardware validation matrix exists and records real tested setups.

### Community Submission

- A concise project description is prepared.
- A demo video or GIF is available.
- The submission email to `research@franka.de` is prepared.
- The project category is clearly proposed.

## 4. Phase 1: GitHub Front Door

Goal: make the repository immediately understandable within 60 seconds.

### Tasks

1. Update README tagline.
2. Add top-level architecture diagram placeholder or final image.
3. Add media section with reserved asset names.
4. Add "Why this project" section:
   - No ROS runtime dependency.
   - Python-native research workflow.
   - Dual-machine design.
   - LeRobot dataset collection.
5. Add "Relationship to ROS" section:
   - This is not a ROS wrapper.
   - This complements, not replaces, `franka_ros`.
   - ROS is better for MoveIt/RViz/TF/ROS-native stacks.
   - This project is better for lightweight Python control and data collection.
6. Add "Feature Map" table:
   - Robot service.
   - Gripper service.
   - `FrankaEnv`.
   - Teleop.
   - Waypoints.
   - Trajectory.
   - Cameras.
   - Data collection.
   - Dataset player.
   - FK/IK.
7. Add links to all docs pages.

### Acceptance Criteria

- A new user can understand what the project does from the README alone.
- A ROS user can understand whether this project is appropriate for them.
- A Franka Community reviewer can identify the project category quickly.

## 5. Phase 2: New-User Quick Start

Goal: a new user can go from clone to first safe test without guessing.

### Tasks

1. Expand `docs/quickstart.md` into three explicit paths:
   - Offline inspection path, no robot required.
   - Control PC service startup path.
   - Algorithm PC teleoperation and data collection path.
2. Explain all IP terms:
   - `--fci-ip`: Franka robot FCI address.
   - `--robot-ip`: control PC address.
   - `--gripper-host`: gripper service host, usually same as `--robot-ip`.
3. Add command blocks for:
   - Installing on algorithm PC.
   - Installing on control PC.
   - Starting `RobotServer`.
   - Starting `GripperServer`.
   - Measuring latency.
   - Running low-speed keyboard teleop.
   - Running low-speed SpaceMouse teleop.
   - Collecting one test episode.
   - Playing back the dataset.
4. Add safety warnings before any command that can move real hardware.
5. Add an "expected output" note for important commands.

### Acceptance Criteria

- All commands are copy-pasteable.
- Every command states which machine should run it.
- A user can understand the network architecture without reading source code.

## 6. Phase 3: Troubleshooting and Hardware Validation

Goal: reduce support burden and build reviewer trust.

### Add `docs/troubleshooting.md`

Required sections:

- Robot server connection failures.
- `--fci-ip` vs `--robot-ip` mistakes.
- ZMQ port conflicts.
- Gripper service failures.
- RealSense device not found.
- SpaceMouse permission problems.
- Keyboard focus and terminal input problems.
- OpenCV GUI vs headless environment problems.
- LeRobot dataset creation/resume errors.
- Unsafe or unexpected robot motion checklist.

### Add `docs/hardware_validation.md`

Required table:

| Item | Tested Value |
|---|---|
| Robot | Franka Research 3 |
| Franka system version | Fill after validation |
| Control PC OS | Fill after validation |
| Kernel | PREEMPT_RT version |
| Algorithm PC OS | Fill after validation |
| Python | 3.12 |
| RealSense cameras | D435/D405/etc. |
| Teleop devices | Keyboard/SpaceMouse model |
| Control modes | `ee_delta`, `joint_delta`, etc. |
| Data collection FPS | 30/60/etc. |

Required validation checklist:

- RobotServer starts.
- GripperServer starts.
- Latency measurement works.
- Keyboard teleop works at low speed.
- SpaceMouse teleop works at low speed.
- Waypoint collection works.
- Trajectory dry-run works.
- Trajectory execution works on a safe route.
- Camera preview works.
- Data collection works with cameras.
- Data collection works with `--no-camera`.
- Dataset player opens and plays dataset.
- Blocking gripper operations do not freeze recorded camera frames.

### Acceptance Criteria

- A reviewer can see exactly what hardware has been tested.
- Users can solve common setup issues without opening source code.

## 7. Phase 4: CI and Quality Gates

Goal: make the project look and behave like a maintained open-source repository.

### Add `.github/workflows/ci.yml`

Recommended CI jobs:

1. Python 3.12 install.
2. `pip install -e ".[dev]"`.
3. `python -m pytest tests -q`.
4. `python -m py_compile` for important scripts:
   - `franka_control/scripts/collect_episodes.py`
   - `franka_control/scripts/teleop.py`
   - `franka_control/scripts/run_trajectory.py`
   - `scripts/play_dataset.py`
5. CLI smoke tests:
   - `python -m franka_control.robot --help`
   - `python -m franka_control.gripper --help`
   - `python -m franka_control.scripts.teleop --help`
   - `python -m franka_control.scripts.collect_episodes --help`
   - `python -m franka_control.scripts.collect_waypoints --help`
   - `python -m franka_control.scripts.run_trajectory --help`
6. Markdown relative link check.

### Add Linting

Recommended:

```bash
ruff check franka_control scripts tests
```

If strict linting creates too much churn, start with a limited ruleset and expand
after the repository stabilizes.

### Acceptance Criteria

- Every pull request runs CI.
- CI does not require robot hardware.
- CI catches broken imports, broken script entry points, and broken docs links.

## 8. Phase 5: Open-Source Project Hygiene

Goal: make contributions and maintenance predictable.

### Add `CHANGELOG.md`

Use "Keep a Changelog" style:

```markdown
# Changelog

## [0.1.0] - YYYY-MM-DD

### Added
- No-ROS dual-machine Franka control stack.
- Gymnasium `FrankaEnv`.
- Teleoperation.
- Trajectory tools.
- LeRobot data collection.
```

### Add `ROADMAP.md`

Recommended sections:

- v0.1: stable no-ROS data collection stack.
- v0.2: stronger safety wrappers and validation tooling.
- v0.3: richer dataset tools and calibration helpers.
- Future: optional ROS bridge, simulation bridge, hand-eye calibration, policy
  deployment examples.

### Add GitHub Issue Templates

Recommended files:

- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/hardware_issue.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`

Hardware issue template should request:

- Robot model.
- Franka system version.
- OS and kernel.
- Python version.
- Exact command.
- Full error log.
- Whether the robot moved.
- Whether emergency stop was needed.

### Add Pull Request Template

Recommended file:

- `.github/pull_request_template.md`

Required checklist:

- Tests run.
- CLI help checks run if scripts changed.
- Docs updated if user-facing behavior changed.
- Hardware tested or explicitly marked offline-only.
- Safety impact described if robot motion changed.

### Acceptance Criteria

- Users know how to report issues.
- Contributors know the quality bar.
- Maintainers can triage hardware issues efficiently.

## 9. Phase 6: Demo Media

Goal: make the project visually credible for GitHub and Franka Community.

### Required Assets

Store under `docs/assets/`:

| File | Purpose |
|---|---|
| `system-architecture.png` | Dual-machine ZMQ architecture |
| `teleop-preview.gif` | Keyboard or SpaceMouse teleop demo |
| `data-collection-preview.gif` | RealSense preview during episode collection |
| `dataset-player.png` | Dataset player with HUD |
| `trajectory-analysis.png` | Joint/EE/gripper trajectory visualization |

### Guidelines

- Keep GIFs short, ideally 5-15 seconds.
- Do not show unsafe robot motion.
- Use low-speed demos.
- Blur or avoid private lab information.
- Prefer one clean task, e.g. pick-and-place or reach-and-grasp.

### Acceptance Criteria

- README top section has visual evidence.
- A reviewer can understand the workflow without running the code.

## 10. Phase 7: First Release

Goal: publish a stable baseline that can be cited and reviewed.

### Tasks

1. Confirm tests pass.
2. Confirm docs links pass.
3. Confirm hardware validation table is filled.
4. Update `CHANGELOG.md`.
5. Tag release:

```bash
git tag -a v0.1.0 -m "v0.1.0"
git push origin v0.1.0
```

6. Create GitHub Release:
   - Title: `v0.1.0 - No-ROS Franka Research 3 Control and Data Collection`
   - Include highlights.
   - Include known limitations.
   - Attach demo video or link.

### Release Notes Template

```markdown
## Highlights

- No-ROS dual-machine control stack for Franka Research 3.
- Gymnasium-compatible `FrankaEnv`.
- Keyboard and SpaceMouse teleoperation.
- Waypoint and TOPPRA trajectory tools.
- RealSense camera integration.
- LeRobot v3 data collection and playback.

## Tested Hardware

- Fill from `docs/hardware_validation.md`.

## Known Limitations

- Not an official Franka Robotics project.
- No ROS TF/RViz/MoveIt integration.
- Real robot use requires careful local safety validation.
```

### Acceptance Criteria

- A stable release URL exists.
- `CITATION.cff` points to the project and version.
- Franka Community submission can reference a specific release.

## 11. Phase 8: Franka Community Submission

Goal: prepare a complete, professional submission.

### Proposed Category

Primary:

- Robot Control & Motion Planning

Secondary:

- Learning Environments and Datasets

### Short Description

```text
Franka Control is an all-in-one, no-ROS Python stack for Franka Research 3
control, teleoperation, motion planning, IK, RealSense integration, and LeRobot
data collection. It uses a dual-machine architecture with ZMQ-based robot and
gripper services, provides a Gymnasium-compatible environment for policies, and
includes tools for SpaceMouse/keyboard teleoperation, waypoint capture,
trajectory execution, synchronized multi-camera demonstration collection, and
dataset playback/analysis.
```

### Submission Email Draft

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

### Acceptance Criteria

- Email includes repository, release, demo, and clear category.
- README is polished before sending.
- Hardware validation is filled before sending.

## 12. Maintenance Rules

To keep the repository credible after publication:

- Do not merge hardware-facing changes without documenting safety implications.
- Keep CLI examples synchronized with actual `--help`.
- Keep README concise and move details into docs.
- Maintain a changelog for user-visible changes.
- Prefer small, focused PRs.
- Add tests for data format, teleop input semantics, and recorder behavior.
- Treat silent data misalignment as a critical bug.
- Treat unsafe motion behavior as a critical bug.

## 13. Recommended Execution Order

1. Add troubleshooting and hardware validation docs.
2. Add CI workflow and link checker.
3. Add roadmap, changelog, issue templates, and PR template.
4. Create architecture diagram and initial screenshots.
5. Run hardware validation and fill the matrix.
6. Polish README with real media.
7. Tag `v0.1.0`.
8. Submit to Franka Community.

## 14. Immediate Next PR Scope

The next concrete change should be:

- `docs/troubleshooting.md`
- `docs/hardware_validation.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `.github/workflows/ci.yml`
- `.github/ISSUE_TEMPLATE/bug_report.yml`
- `.github/ISSUE_TEMPLATE/hardware_issue.yml`
- `.github/ISSUE_TEMPLATE/feature_request.yml`
- `.github/pull_request_template.md`
- README update linking these files

This scope is high leverage because it turns the project from a strong personal
research repository into a community-ready open-source project.
