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
- GitHub Actions has not run on the remote repository yet.
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

Push the current community-readiness batch, then confirm GitHub Actions on
`origin/main`. After CI is green, collect real FR3 validation values and capture
the remaining README media assets.
