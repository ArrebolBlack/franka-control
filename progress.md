# Progress Log

This file records what happened in each iteration, what changed, and what is
still blocked. Keep entries factual and short.

## 2026-04-27: English README and Open-Source Metadata

### Completed

- Reworked the main README into an English GitHub-facing entry point.
- Preserved the Chinese README as `README.zh-CN.md`.
- Added documentation pages:
  - `docs/README.md`
  - `docs/quickstart.md`
  - `docs/data_collection.md`
  - `docs/api.md`
  - `docs/ros_comparison.md`
  - `docs/assets/README.md`
- Added open-source metadata:
  - `LICENSE`
  - `CITATION.cff`
  - `CONTRIBUTING.md`
  - `SECURITY.md`
- Updated package metadata in `pyproject.toml`.
- Added `matplotlib` dependency for dataset visualization.

### Validation

- `git diff --check` passed.
- `python -m py_compile` passed for important scripts.
- `python -m pytest tests -q` passed with 47 tests.
- `conda run -n franka python -m franka_control.scripts.collect_episodes --help` passed.
- `conda run -n franka python scripts/play_dataset.py --help` passed.
- Markdown relative link check passed.

### Committed

- Commit: `618a795 docs: add English README and project metadata`
- Pushed to `origin/main`.

### Remaining

- Real screenshots and GIFs are still missing.
- CI workflow is still missing.
- Hardware validation matrix is still missing.
- Roadmap and changelog are still missing.

## 2026-04-28: Community Readiness Plan

### Completed

- Reviewed project positioning for Franka Community submission.
- Defined the repository as an all-in-one, no-ROS Python stack for FR3 control,
  teleoperation, motion planning, IK, RealSense integration, and LeRobot data
  collection.
- Added `plan.md` with:
  - Project positioning.
  - Definition of done.
  - Documentation tasks.
  - CI tasks.
  - Open-source hygiene tasks.
  - Demo media tasks.
  - Release plan.
  - Franka Community submission email draft.

### Validation

- `git diff --check` passed.

### Remaining

- `plan.md` is not committed yet.
- Need to add task tracking docs:
  - `goal.md`
  - `todo.md`
  - `progress.md`
  - `acceptance.md`

## 2026-04-28: Project Management Docs

### Completed

- Added `goal.md` to define task goal, scope, boundaries, non-goals, and safety
  limits.
- Added `todo.md` to track task breakdown and current status.
- Added `progress.md` to record per-iteration progress and blockers.
- Added `acceptance.md` to define measurable acceptance criteria.

### Validation

- Pending after file creation:
  - `git diff --check`
  - Markdown link check if links are added or changed.

### Current Blockers

- Real hardware validation requires access to the FR3 setup.
- Real screenshots/GIFs require a safe demo scene and camera/display setup.
- GitHub release should wait until CI and hardware validation docs are complete.

## 2026-04-28: Community-Readiness Implementation Batch

### Completed

- Added user-facing readiness docs:
  - `docs/troubleshooting.md`
  - `docs/hardware_validation.md`
  - `docs/community_submission.md`
- Reworked `docs/quickstart.md` into three explicit paths:
  - offline inspection,
  - control PC services,
  - algorithm PC teleoperation and data collection.
- Added release and maintenance docs:
  - `ROADMAP.md`
  - `CHANGELOG.md`
- Added CI and offline quality tooling:
  - `.github/workflows/ci.yml`
  - `scripts/check_markdown_links.py`
  - limited `ruff` configuration in `pyproject.toml`.
- Added GitHub collaboration templates:
  - `.github/ISSUE_TEMPLATE/bug_report.yml`
  - `.github/ISSUE_TEMPLATE/hardware_issue.yml`
  - `.github/ISSUE_TEMPLATE/feature_request.yml`
  - `.github/pull_request_template.md`
- Added `--gripper-host` and `--gripper-port` to
  `franka_control.scripts.collect_episodes` so data collection matches the
  documented dual-machine model.
- Updated README and docs index links for the new documentation.
- Made `scripts/play_dataset.py --help` work even when GUI/player runtime
  dependencies are missing, so CLI smoke tests can run in lean environments.
- Generated and linked `docs/assets/system-architecture.png`.

### Validation

- `git diff --check` passed.
- `python scripts/check_markdown_links.py` passed.
- `python -m py_compile franka_control/scripts/collect_episodes.py franka_control/scripts/teleop.py franka_control/scripts/run_trajectory.py scripts/play_dataset.py scripts/check_markdown_links.py` passed.
- `python -m pytest tests -q` passed with 47 tests.
- CLI `--help` smoke tests passed for:
  - `python -m franka_control.robot --help`
  - `python -m franka_control.gripper --help`
  - `python -m franka_control.scripts.teleop --help`
  - `python -m franka_control.scripts.collect_episodes --help`
  - `python -m franka_control.scripts.collect_waypoints --help`
  - `python -m franka_control.scripts.run_trajectory --help`
  - `python -m franka_control.scripts.measure_latency --help`
  - `python scripts/play_dataset.py --help`
- `python -m ruff check franka_control scripts tests` passed after installing
  `ruff` in the local user Python environment.

### Remaining

- Community-readiness batch committed locally as
  `f988044 docs: add community readiness gates`.
- Memory update committed locally as
  `372432a docs: record community readiness commit`.
- Both commits were pushed to `origin/main`.
- GitHub Actions run `25048732038` failed in the Markdown link check because
  `docs/README.md` linked ignored local files that were not present on the
  runner: `docs/com_estimation_algorithm.md` and `docs/solve_com.py`.
- The ignored local-file links were removed from `docs/README.md`.
- Markdown-link fix committed and pushed as
  `b91d53a docs: fix markdown links for ci`.
- GitHub Actions run `25048952721` passed on `origin/main`.
- CI badge/status update committed and pushed as
  `3490ac0 docs: record green ci status`.
- GitHub Actions run `25049184348` passed on `origin/main`.
- CI emitted a non-blocking Node.js 20 deprecation warning for
  `actions/checkout@v4` and `actions/setup-python@v5`. Official releases show
  `actions/checkout@v6.0.2` and `actions/setup-python@v6.2.0`; workflow upgrade
  was committed and pushed as `ddd53e5 ci: update github actions versions`.
- GitHub Actions run `25049362136` passed on `origin/main` after the Actions v6
  upgrade.
- Real hardware validation values are still pending FR3 access.
- Real screenshots/GIFs are still missing.
- `docs/assets/system-architecture.png` exists, but teleop, data collection,
  dataset player, and trajectory analysis media still need real captures.
- `v0.1.0` release is still pending.

## Active Risks

- Documentation may overclaim if hardware validation is not filled with exact
  tested versions.
- OpenCV GUI/headless environment confusion is now documented, but still needs
  validation on the lab machines.
- Franka Community submission should not be sent before demo media and release
  are ready.

## Next Recommended Iteration

Collect real FR3 validation values and capture the remaining README media
assets. Release and Franka Community submission remain blocked until those
external artifacts are complete.

## 2026-04-29: GitHub Repository Metadata and Release Tracking

### Completed

- Updated GitHub About description to:
  `No-ROS Python stack for Franka Research 3 control, teleoperation, trajectory planning, IK, RealSense, and LeRobot data collection.`
- Added GitHub topics:
  - `franka`
  - `franka-research-3`
  - `robot-control`
  - `robotics`
  - `teleoperation`
  - `motion-planning`
  - `inverse-kinematics`
  - `gymnasium`
  - `realsense`
  - `lerobot`
  - `imitation-learning`
  - `reinforcement-learning`
  - `no-ros`
- Added GitHub labels:
  - `hardware`
  - `safety`
  - `data`
  - `docs`
  - `needs validation`
- Created GitHub milestone `v0.1.0`.
- Created release-blocker issues:
  - `#1` Capture README demo media assets.
  - `#2` Fill hardware validation matrix for FR3 setup.
  - `#3` Prepare v0.1.0 release.
  - `#4` Finalize Franka Community submission.

### Validation

- `gh repo view` confirmed About description and topics.
- `gh label list` confirmed required labels.
- `gh issue list` confirmed the four open milestone issues.

### Remaining

- Issues `#1` and `#2` require real hardware/media work.
- Issue `#3` waits on `#1` and `#2`.
- Issue `#4` waits on the `v0.1.0` release and demo URL.

## 2026-04-29: Hardware Validation Helper

### Completed

- Added `scripts/collect_validation_info.py` to collect machine, Python, git,
  package-version, and optional RealSense details for
  `docs/hardware_validation.md`.
- Documented the helper in `docs/hardware_validation.md` and `docs/README.md`.
- Added compile and `--help` smoke coverage for the helper in CI.

### Validation

- Local checks passed:
  - `python scripts/collect_validation_info.py --help`
  - `python scripts/collect_validation_info.py --format json`
  - `python scripts/collect_validation_info.py --format markdown`
  - `python -m py_compile ... scripts/collect_validation_info.py`
  - `python scripts/check_markdown_links.py`
  - `git diff --check`
  - `python -m ruff check franka_control scripts tests`
  - `python -m pytest tests -q`
- Committed and pushed as
  `77effa3 tools: add hardware validation info helper`.
- GitHub Actions run `25071752853` passed on `origin/main`.

### Remaining

- The helper still needs to be run on the actual control PC and algorithm PC.
- Real robot validation remains blocked on FR3 access.

## 2026-04-29: Media Capture Runbook

### Completed

- Added `docs/media_capture.md` with safe capture instructions for:
  - `docs/assets/teleop-preview.gif`
  - `docs/assets/data-collection-preview.gif`
  - `docs/assets/dataset-player.png`
  - `docs/assets/trajectory-analysis.png`
- Linked the runbook from `README.md`, `docs/README.md`, and
  `docs/assets/README.md`.

### Remaining

- Actual media capture still requires real hardware and a safe lab scene.

## 2026-04-29: Release Materials Checklist

### Completed

- Added `docs/release_materials_checklist.md` as a Chinese collection checklist
  for:
  - network and hardware baseline information,
  - control PC and algorithm PC environment outputs,
  - hardware validation evidence,
  - README screenshots, GIFs, and optional demo video,
  - release and Franka Community submission inputs.
- Linked the checklist from `README.md`, `docs/README.md`, and
  `docs/assets/README.md`.
- Updated `goal.md`, `plan.md`, `acceptance.md`, and `todo.md` to record the
  new external-materials checklist.

### Remaining

- The checklist still needs to be filled by running the real FR3 validation
  workflow and capturing the requested media assets.

## 2026-04-29: Hardware Setup and Environment Values

### Completed

- Recorded initial real setup values in `docs/hardware_validation.md`:
  - Franka FCI IP `172.16.0.2`.
  - Control PC IP `10.100.79.71`.
  - Algorithm PC IP `10.100.74.202`.
  - Franka Research 3 `Arm3Rv2`.
  - Franka Control `5.9.2` and system image `5.9.2`.
  - Franka Hand with default configuration.
  - Control PC Ubuntu 24.04.4 LTS with `6.8.1-1046-realtime` PREEMPT_RT
    kernel.
  - Algorithm PC Ubuntu 24.04.4 LTS with `6.17.0-22-generic` kernel.
  - Control PC and algorithm PC Python/package environment outputs.
  - Intel RealSense D405 and D435 camera details.
  - Standard keyboard and 3Dconnexion SpaceMouse Compact device details.
- Confirmed service default ports from source:
  - Robot RPC `5555`.
  - Gripper RPC `5556`.
  - Robot state stream `5557`.
- Updated `todo.md`, `acceptance.md`, `goal.md`, and `plan.md` to reflect
  that setup/environment details are recorded while functional validation is
  still pending.

### Remaining

- Re-run the environment helper after both machines are synchronized to the same
  commit; the provided outputs reported `99a8d9c` on the control PC and
  `63b029c` on the algorithm PC.
- Functional hardware validation is still pending:
  `RobotServer`, `GripperServer`, latency, teleop, waypoint, trajectory,
  camera preview, data collection, dataset player, and blocking-gripper checks.
- Real README screenshots/GIFs are still pending.

## 2026-04-29: Core Hardware Workflow Validation

### Completed

- Recorded successful real FR3 validation results in
  `docs/hardware_validation.md` for:
  - `RobotServer` startup on port `5555`.
  - `GripperServer` startup on port `5556`.
  - latency measurement from algorithm PC to control PC.
  - low-speed keyboard teleoperation.
  - low-speed SpaceMouse teleoperation.
  - waypoint collection into `test_output/test_waypoints.yaml`.
  - trajectory dry-run and safe trajectory execution for `test-route-2`.
  - RealSense camera preview and data collection with `config/cameras.yaml`.
  - state/action data collection with `--no-camera`.
  - dataset playback for both camera and no-camera datasets.
- Recorded the observed latency statistics, including high tail-latency spikes.
- Updated public example commands to include conservative
  `--action-scale-t 0.5 --action-scale-r 1.0` values for data collection and
  first-run demos.
- Documented that existing dataset roots require `--resume` or a fresh
  `--repo-id` / `--root`.
- Updated `todo.md`, `acceptance.md`, `goal.md`, and `plan.md` to reflect that
  core workflow validation is recorded.

### Remaining

- Blocking gripper camera-frame continuity was completed in the next entry.
- The real README screenshots/GIFs are still pending.
- Final release should still wait for media, final redaction, and a synchronized
  commit/environment re-check on both machines.

## 2026-04-29: Blocking Gripper Camera-Frame Validation

### Completed

- Recorded the final hardware checklist item in `docs/hardware_validation.md`:
  blocking gripper open/close/grasp calls do not freeze recorded camera frames.
- Documented the observed behavior:
  - the CV2 realtime preview window can block during the gripper operation,
  - the saved dataset remains normal and should be used as the validation source.
- Updated `docs/data_collection.md` and `docs/release_materials_checklist.md`
  with the same distinction between realtime preview smoothness and saved
  dataset correctness.
- Updated `todo.md`, `acceptance.md`, `goal.md`, and `plan.md` to mark
  hardware validation as filled.

### Remaining

- Real README screenshots/GIFs are still pending.
- Final release still needs a public redaction pass over local network,
  hostname, filesystem path, and camera serial details.
- Re-run the environment helper after both machines are synchronized to the same
  release commit.
