# Acceptance Criteria

This file defines measurable acceptance criteria for making `franka-control`
ready for Franka Community submission.

## Current Acceptance Status

As of 2026-04-28:

- Repository identity: mostly complete locally; GitHub About text still needs to
  be set in the GitHub UI.
- Documentation completeness: required files exist locally and are linked from
  README or `docs/README.md`.
- New-user quick start: complete locally with offline, control-PC, and
  algorithm-PC paths.
- ROS relationship: documented in README and `docs/ros_comparison.md`.
- Hardware validation: matrix exists, but real tested values are still pending.
- CI and offline quality gates: workflow and local checks are configured; remote
  GitHub Actions status is pending.
- Open-source hygiene: required files and templates exist locally.
- Demo media: system architecture image exists; real workflow screenshots/GIFs
  are still pending.
- Release readiness: blocked until hardware validation, demo media, and remote
  CI are complete.
- Franka Community submission: draft exists, not ready to send.

## 1. Repository Identity

The repository passes this section when:

- The GitHub About text clearly says this is a no-ROS Python stack for Franka
  Research 3.
- The README clearly states what the project does in the first 30 seconds of
  reading.
- The README explains why the project exists and who should use it.
- The README explicitly says the project is not official Franka Robotics
  software.
- The README explicitly says the project complements, not replaces, ROS and
  `franka_ros`.

## 2. Documentation Completeness

The repository passes this section when these files exist and are linked from
README or `docs/README.md`:

- `README.md`
- `README.zh-CN.md`
- `docs/README.md`
- `docs/quickstart.md`
- `docs/data_collection.md`
- `docs/api.md`
- `docs/ros_comparison.md`
- `docs/troubleshooting.md`
- `docs/hardware_validation.md`
- `docs/community_submission.md`
- `docs/assets/README.md`
- `ROADMAP.md`
- `CHANGELOG.md`
- `CONTRIBUTING.md`
- `SECURITY.md`
- `LICENSE`
- `CITATION.cff`

## 3. New-User Quick Start

The repository passes this section when:

- A new user can identify which commands run on the control PC.
- A new user can identify which commands run on the algorithm/GPU PC.
- `--fci-ip`, `--robot-ip`, and `--gripper-host` are explained clearly.
- The quickstart includes:
  - installation,
  - robot server startup,
  - gripper server startup,
  - latency check,
  - keyboard teleop,
  - SpaceMouse teleop,
  - data collection,
  - dataset playback.
- All commands match actual CLI `--help` output.
- Safety warnings appear before any command that can move real hardware.

## 4. ROS Relationship

The repository passes this section when documentation clearly states:

- No ROS runtime is required.
- The project does not use ROS nodes, topics, TF, launch files, or MoveIt.
- `franka_ros` is still preferred for ROS-native workflows.
- `libfranka` remains the lower-level official FCI library.
- `aiofranka` and `pylibfranka` are control-machine dependencies, not required
  on the algorithm machine.
- LeRobot is used for dataset format and tooling.

## 5. Hardware Validation

The repository passes this section when `docs/hardware_validation.md` records:

- Robot model.
- Franka system version.
- Control PC OS.
- Control PC kernel.
- Algorithm PC OS.
- Python version.
- RealSense camera models.
- Teleop device models.
- Tested control modes.
- Tested data collection FPS.

Required validation checklist:

- RobotServer starts successfully.
- GripperServer starts successfully.
- Latency measurement works.
- Keyboard teleop works at low speed.
- SpaceMouse teleop works at low speed.
- Waypoint collection works.
- Trajectory dry-run works.
- Safe trajectory execution works.
- Camera preview works.
- Data collection with cameras works.
- Data collection with `--no-camera` works.
- Dataset player works.
- Blocking gripper calls do not freeze recorded camera frames.

## 6. CI and Offline Quality Gates

The repository passes this section when GitHub Actions runs:

- Python 3.12 setup.
- Editable install.
- Unit tests.
- Python compile checks for important scripts.
- CLI `--help` smoke tests.
- Markdown relative-link check.
- Optional or staged `ruff` linting.

Required local commands before release:

```bash
git diff --check
python -m pytest tests -q
python -m py_compile franka_control/scripts/collect_episodes.py franka_control/scripts/teleop.py franka_control/scripts/run_trajectory.py scripts/play_dataset.py scripts/check_markdown_links.py
python -m franka_control.robot --help
python -m franka_control.gripper --help
python -m franka_control.scripts.teleop --help
python -m franka_control.scripts.collect_episodes --help
python -m franka_control.scripts.collect_waypoints --help
python -m franka_control.scripts.run_trajectory --help
python -m franka_control.scripts.measure_latency --help
python scripts/play_dataset.py --help
python scripts/check_markdown_links.py
python -m ruff check franka_control scripts tests
```

## 7. Open-Source Hygiene

The repository passes this section when:

- `LICENSE` exists.
- `CITATION.cff` exists.
- `CONTRIBUTING.md` exists.
- `SECURITY.md` exists.
- `CHANGELOG.md` exists.
- `ROADMAP.md` exists.
- GitHub issue templates exist.
- Pull request template exists.
- User-facing changes require docs updates.
- Hardware-facing changes require safety notes.

## 8. Demo Media

The repository passes this section when README includes or links to:

- `docs/assets/system-architecture.png`
- `docs/assets/teleop-preview.gif`
- `docs/assets/data-collection-preview.gif`
- `docs/assets/dataset-player.png`
- `docs/assets/trajectory-analysis.png`

Media acceptance:

- The robot motion shown is safe and low-speed.
- The images do not expose sensitive lab information.
- The media demonstrates real workflows, not mock-only behavior.

## 9. Release Readiness

The repository passes this section when:

- All tests pass.
- CI is green.
- Hardware validation is filled.
- Demo media is present.
- `CHANGELOG.md` describes the release.
- A GitHub release exists, starting with `v0.1.0`.
- `CITATION.cff` is aligned with the release.
- Known limitations are documented.

## 10. Franka Community Submission

The project is ready to submit when:

- Repository URL is public.
- Release URL is available.
- Demo URL or GIF is available.
- Short description is ready.
- Suggested categories are clear:
  - Robot Control & Motion Planning.
  - Learning Environments and Datasets.
- Submission email to `research@franka.de` is prepared.

## 11. Final Go / No-Go Checklist

Submit only if all are true:

- `[ ]` README is polished and accurate.
- `[x]` Docs are complete enough for a new user.
- `[ ]` CI is green on GitHub.
- `[ ]` Hardware validation is filled.
- `[ ]` Demo media is available.
- `[ ]` A release exists.
- `[ ]` The project does not overclaim official Franka support.
- `[ ]` The project clearly explains no-ROS scope and ROS relationship.
- `[ ]` Safety limitations are explicit.
