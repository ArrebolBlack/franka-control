# Acceptance Criteria

This file defines measurable acceptance criteria for making `franka-control`
ready for Franka Community submission.

## Current Acceptance Status

As of 2026-04-30:

- Confirmed target: make `franka-control` a high-value open-source project for
  Franka Community submission, with Franky-class public quality but a distinct
  no-ROS FR3 learning/data-collection focus.
- Repository identity: complete; GitHub About description and topics are set.
- Documentation completeness: required files exist locally and are linked from
  README or `docs/README.md`.
- New-user quick start: complete locally with offline, control-PC, and
  algorithm-PC paths.
- ROS relationship: documented in README and `docs/ros_comparison.md`.
- Hardware validation: real setup, machine, dependency, camera, and
  teleop-device values are recorded with public redaction applied; core robot
  workflow validation and blocking-gripper camera-frame validation are
  recorded.
- Release materials checklist: exists and lists the remaining external
  information, validation evidence, screenshots/GIFs, demo video, and submission
  inputs.
- CI and offline quality gates: workflow and local checks are configured; remote
  GitHub Actions run `25119439661` passed on `origin/main`.
- Open-source hygiene: required files and templates exist locally.
- GitHub triage setup: required labels, `v0.1.0` milestone, and release-blocker
  issues exist.
- Demo media: system architecture, keyboard teleop video, SpaceMouse teleop
  video, dataset playback video, trajectory figure, and action distribution
  figure are present.
- Data-collection usability polish: RealSense camera listing/YAML generation,
  existing-dataset guidance, and live collection overlay/FPS reporting are
  complete.
- Repository audit: initial high-risk items are complete locally: wheel package
  data includes kinematics assets, generated demo/test outputs are ignored,
  stale `collect_data.py` was removed, public redaction was applied, and
  offline tests were expanded.
- Release-facing docs: `README.md`, `CHANGELOG.md`, and `CITATION.cff` are
  aligned locally for `v0.1.0` with release date `2026-04-30`.
- Release readiness: blocked until the release tag and GitHub release are
  complete.
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
- `docs/media_capture.md`
- `docs/release_materials_checklist.md`
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

Local status:

- `[x]` Local offline checks passed before commit `f988044`.
- `[x]` GitHub Actions has passed on `origin/main`.
- `[x]` First GitHub Actions run `25048732038` failed on Markdown links to
  ignored local files; fixed by commit `b91d53a`.
- `[x]` GitHub Actions v6 upgrade removed the Node.js 20 deprecation warning;
  run `25049362136` passed.
- `[x]` Hardware validation helper is covered by CI; run `25071752853` passed.
- `[x]` RealSense camera listing and data-collection usability polish are
  covered by CI; run `25119439661` passed.

Required local commands before release:

```bash
git diff --check
python -m pytest tests -q
python -m py_compile franka_control/scripts/collect_episodes.py franka_control/scripts/teleop.py franka_control/scripts/run_trajectory.py franka_control/cameras/list_cameras.py scripts/play_dataset.py scripts/collect_validation_info.py scripts/check_markdown_links.py
python -m franka_control.robot --help
python -m franka_control.gripper --help
python -m franka_control.scripts.teleop --help
python -m franka_control.scripts.collect_episodes --help
python -m franka_control.scripts.collect_waypoints --help
python -m franka_control.scripts.run_trajectory --help
python -m franka_control.scripts.measure_latency --help
python -m franka_control.cameras.list_cameras --help
python scripts/play_dataset.py --help
python scripts/collect_validation_info.py --help
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

GitHub tracking status:

- `[x]` Required labels exist.
- `[x]` Milestone `v0.1.0` exists.
- `[x]` Release-blocker issues `#1` through `#4` exist.
- `[x]` Issue `#1` README demo media is closed after adding final assets.
- `[x]` Issue `#2` hardware validation is closed after filling
  `docs/hardware_validation.md`.

## 8. Demo Media

The repository passes this section when README includes or links to:

- `docs/assets/system-architecture.png`
- `docs/assets/keyboard-teleop-install-gear.mp4`
- `docs/assets/spacemouse-teleop-pouring.mp4`
- `docs/assets/dataset-player-fruit-basket.mp4`
- `docs/assets/trajectory-analysis.png`
- `docs/assets/action-distribution.png`

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

- `[x]` README is polished and accurate.
- `[x]` Docs are complete enough for a new user.
- `[x]` CI is green on GitHub.
- `[x]` Hardware validation is filled.
- `[x]` Demo media is available.
- `[ ]` A release exists.
- `[x]` The project does not overclaim official Franka support.
- `[x]` The project clearly explains no-ROS scope and ROS relationship.
- `[x]` Safety limitations are explicit.

## 12. High-Value Open-Source Polish

The repository passes this section when:

- The README communicates the value proposition in the first 30 seconds.
- The architecture diagram matches the actual dual-machine ZMQ implementation
  and the documented data-collection/planning/analysis workflow.
- The repository has a clear policy for demo data, test output, generated
  files, and release media.
- Source distributions and wheels include required non-Python runtime assets,
  especially the bundled URDF and mesh files used by `IKSolver`.
- Public docs do not expose private hostnames, local user paths, camera serials,
  or lab network details.
- Deprecated or historical scripts are either removed, documented as legacy, or
  redirected to the supported workflow.
- Offline tests cover the highest-risk non-hardware behavior that can be tested
  without an FR3.
- Any hardware-facing change has an approved modification plan, risk note, and
  validation procedure before implementation.
- Git commit author/committer identity is checked before every release commit;
  contributors must not appear as Claude or any AI assistant identity.
