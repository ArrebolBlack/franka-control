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
- Commented on and closed GitHub issue `#2`
  (`Fill hardware validation matrix for FR3 setup`).

### Remaining

- Real README screenshots/GIFs are still pending.
- Final release still needs a public redaction pass over local network,
  hostname, filesystem path, and camera serial details.
- Re-run the environment helper after both machines are synchronized to the same
  release commit.

## 2026-04-29: README Demo Media Assets

### Completed

- Added final README media assets under `docs/assets/`:
  - `keyboard-teleop-install-gear.mp4`
  - `spacemouse-teleop-pouring.mp4`
  - `dataset-player-fruit-basket.mp4`
  - `trajectory-analysis.png`
  - `action-distribution.png`
- Updated `README.md` to link keyboard teleoperation, SpaceMouse teleoperation,
  dataset playback, trajectory analysis, action distribution, and architecture
  assets.
- Updated `docs/assets/README.md`, `docs/media_capture.md`,
  `docs/release_materials_checklist.md`, `docs/community_submission.md`,
  `acceptance.md`, `todo.md`, `goal.md`, and `plan.md` for the new media plan.
- Dropped `data-collection-preview.gif` from the required `v0.1.0` media set;
  it remains optional because dataset playback and hardware validation already
  demonstrate camera-backed collection.
- Commented on and closed GitHub issue `#1`
  (`Capture README demo media assets`).

### Remaining

- Final release still needs public redaction and release creation.

## 2026-04-29: Data Collection Usability Polish

### Completed

- Added `python -m franka_control.cameras.list_cameras` to list connected
  RealSense devices and print starter `config/cameras.yaml` snippets.
- Added unit tests for the RealSense camera-listing helper.
- Improved `DataCollector`'s existing-dataset error message so users know to
  pass `--resume` or choose a fresh dataset root.
- Improved `collect_episodes` OpenCV overlay text and FPS reporting during
  preview/recording.
- Documented the camera listing helper in `docs/data_collection.md`,
  `docs/quickstart.md`, `docs/README.md`, and the release checklist.

### Validation

- `python -m pytest tests -q` passed with 49 tests.
- `python -m ruff check franka_control scripts tests` passed.
- `python -m py_compile franka_control/data/collector.py franka_control/scripts/collect_episodes.py franka_control/cameras/list_cameras.py` passed.
- `python -m franka_control.cameras.list_cameras --help` passed.
- `python -m franka_control.cameras.list_cameras --format yaml` printed the
  detected RealSense devices as a YAML snippet.
- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.

### Remaining

- Keep generated demo datasets and test outputs local; they are intentionally
  not part of the release commit.

## 2026-04-30: Overall Plan Review

### Completed

- Rechecked `plan.md`, `goal.md`, `progress.md`, `acceptance.md`, and
  `todo.md` against the current repository state.
- Confirmed open GitHub release-blocker issues are only:
  - `#3` Prepare v0.1.0 release.
  - `#4` Finalize Franka Community submission.
- Confirmed latest GitHub Actions run `25119439661` passed on `origin/main`.
- Confirmed local untracked directories are still limited to `demo/` and
  `test_output/`, which should remain local and uncommitted.

### Remaining

- Final public redaction pass over documentation and release notes.
- Finalize `CHANGELOG.md` and align `CITATION.cff` with the actual release date.
- Rerun release checks.
- Tag and publish `v0.1.0`.
- Finalize and send the Franka Community submission after release.

## 2026-04-30: Goal Confirmation and Readiness Audit

### Completed

- Confirmed the target: turn `franka-control` into a high-value open-source
  repository suitable for Franka Community submission, comparable in public
  quality to classic community projects such as Franky.
- Confirmed the project boundary: no-ROS Python-native FR3 control,
  teleoperation, trajectory execution, RealSense integration, LeRobot data
  collection, dataset playback, and visualization.
- Confirmed collaboration rule: code changes require a file-level modification
  plan, user approval, and validation plan before implementation.
- Added contributor identity rules to `CLAUDE.md`: commits/releases/PRs must
  use the `ArrebolBlack` GitHub identity, not Claude or any AI assistant
  identity.
- Ran local offline checks:
  - `python -m pytest tests -q` passed with 49 tests.
  - `python scripts/check_markdown_links.py` passed.
  - `git diff --check` passed.
  - `python -m ruff check franka_control scripts tests` passed.
- Updated `goal.md`, `todo.md`, and `acceptance.md` with the confirmed target,
  boundaries, open-source polish criteria, and next audit tasks.

### Findings

- `franka_control/kinematics/assets/` is tracked by git, but current packaging
  metadata does not yet clearly include URDF/mesh assets in built
  distributions.
- `docs/hardware_validation.md` contains real hostnames, local paths, IP
  addresses, and setup details that need final public redaction before release.
- `demo/` and `test_output/` contain untracked generated LeRobot/demo artifacts;
  release policy needs to be decided before publishing.
- `franka_control/scripts/collect_data.py` appears to be an older collection
  entry point and should be reviewed before public release.

### Remaining

- Produce a file-level change proposal for packaging, cleanup, tests, redaction,
  and README/architecture polish before any code edits.
- Wait for user approval before changing behavior or removing files.

## 2026-04-30: Repository Audit and Change Proposal Baseline

### Current Subtask

Repository audit for release blockers and high-value open-source polish.

### This Round's Method

- Checked contributor identity:
  - `git config user.name` -> `ArrebolBlack`
  - `git config user.email` -> `2078004110@qq.com`
- Built a temporary wheel with:
  - `python -m pip wheel . -w /tmp/franka-control-wheel-audit --no-deps`
- Inspected wheel contents with `unzip -l`.
- Checked tracked files, untracked generated files, ignored files, package size,
  public-redaction hits, and old/TBD markers.
- Read the old `franka_control/scripts/collect_data.py` entry point and current
  data-collection tests.

### Results

- Temporary wheel builds, but it is only about 88K and contains no
  `franka_control/kinematics/assets` files. A wheel install would break the
  default `IKSolver()` because the bundled URDF/mesh files are missing.
- `franka_control/kinematics/assets/` is tracked and is about 189M, so the
  release needs an explicit decision: package all required assets, package only
  the minimal FR3v2 subset needed by the default solver, or document/edit the
  asset strategy.
- `docs/assets/` is about 64M and already contains the intended README media.
- `demo/` is about 299M and `test_output/` is about 5M. Their `data/` and
  `videos/` subtrees are ignored by the existing `data/`, `videos/`, and
  `screenshots/` ignore rules, but `meta/` files are currently untracked and
  visible in `git status`.
- `docs/hardware_validation.md` contains real hostnames, local paths, real lab
  IPs, and command examples using those values. This remains a release blocker
  until public redaction is done.
- `franka_control/scripts/collect_data.py` appears stale: it calls the old
  `DataCollector(repo_id=..., fps=..., cameras=...)` style API, while the
  current collector requires `DataCollector(CollectionConfig, ...)`.
- Current local checks remain green:
  - `python -m pytest tests -q` passed with 49 tests.
  - `python scripts/check_markdown_links.py` passed.
  - `git diff --check` passed.
  - `python -m ruff check franka_control scripts tests` passed.

### Proposed File-Level Change Plan

No code change has been executed yet. Proposed changes for user approval:

- `pyproject.toml` plus optional `MANIFEST.in`: include required URDF/mesh
  package data in built wheels and source distributions. Validate by rebuilding
  a wheel and checking for `franka_control/kinematics/assets/fr3v2.urdf`.
- `franka_control/scripts/collect_data.py`: remove the stale entry point,
  convert it into a compatibility wrapper that exits with a clear deprecation
  message, or update it to call the current `CollectionConfig` workflow.
  Recommended: deprecate or remove, because `collect_episodes.py` is the
  documented supported workflow.
- `.gitignore`: explicitly ignore generated `demo/` and `test_output/`
  dataset metadata unless the project decides to commit curated public samples.
- `docs/hardware_validation.md`: redact hostnames, local paths, real lab IPs,
  and serial-like values while preserving validation credibility.
- Tests: add offline tests for package asset availability, trajectory route
  splitting/planning validation, state-recorder conversion, and environment
  action-shape/clip logic where mocking is safe.

### Done Criteria for This Round

- The audit has produced concrete file-level proposals.
- The current repository baseline remains green.
- The next step is blocked only on user approval for the proposed code and
  structural edits.

## 2026-04-30: Approved Release-Readiness Fix Batch

### Current Subtask

Execute the approved first batch of release-readiness fixes.

### This Round's Method

- Implemented only the user-approved changes:
  - Include kinematics assets in default packaging.
  - Delete the stale `collect_data.py` entry point if confirmed unused.
  - Keep `demo/` and `test_output/` local by updating `.gitignore`.
  - Redact public docs.
  - Add offline tests for high-risk non-hardware behavior.
- Rebuilt a temporary wheel and inspected its contents.
- Re-ran local tests, lint, markdown links, compile checks, CLI help smoke
  tests, and sensitive-value scans.

### Changes Made

- Added `MANIFEST.in`.
- Updated `pyproject.toml` with `include-package-data` and package-data entries
  for `franka_control.kinematics/assets`.
- Deleted stale `franka_control/scripts/collect_data.py`. It was not referenced
  by README, docs, tests, or CI, and it called the old `DataCollector` API.
- Updated `.gitignore` to ignore generated `demo/` and `test_output/`
  directories.
- Redacted `docs/hardware_validation.md` and related examples to remove real
  hostnames, local paths, lab IPs, and camera serial numbers.
- Replaced serial/IP examples in `docs/data_collection.md` and selected code
  docstrings with placeholders.
- Added offline tests:
  - `tests/test_kinematics_assets.py`
  - `tests/test_state_recorder.py`
  - `tests/test_trajectory.py`
  - `tests/test_franka_env_logic.py`

### Validation

- `python -m pytest tests -q` passed with 56 tests.
- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.
- `python -m py_compile ...` passed for important scripts and helpers.
- `python -m ruff check franka_control scripts tests` passed.
- CLI `--help` smoke tests passed for robot, gripper, teleop,
  `collect_episodes`, `collect_waypoints`, `run_trajectory`,
  `measure_latency`, camera listing, dataset player, and validation-info
  helper.
- Temporary wheel validation:
  - Command: `python -m pip wheel . -w /tmp/franka-control-wheel-audit-fixed --no-deps`
  - Wheel size: about 52M.
  - Wheel contains `franka_control/kinematics/assets/fr3v2.urdf`.
  - Wheel contains required FR3v2 mesh files such as `link0.dae` and
    `link0.stl`.
- Sensitive-value scan no longer finds the previously identified real hostnames,
  local paths, lab IPs, or camera serials.
- `git status --short -uall` no longer shows untracked generated files under
  `demo/` or `test_output/`.

### Remaining

- Review whether the final architecture diagram still matches the code.
- Finalize `CHANGELOG.md` and align `CITATION.cff` with the actual release date.
- Rerun full release checks after any remaining README/release-note changes.
- Tag and publish `v0.1.0`, then finalize Franka Community submission.

## 2026-04-30: Architecture Review and Diagram Comparison

### Current Subtask

Carefully inspect the code architecture and compare it with the current
architecture documentation/diagram before the final README and release polish.

### This Round's Method

- Traced the main runtime paths:
  - `RobotServer`/`RobotClient`.
  - `GripperServer`/`GripperClient`.
  - `FrankaEnv`.
  - `collect_episodes.py`.
  - `StateStreamRecorder`.
  - `CameraManager`.
  - teleoperation providers.
  - trajectory planning/execution.
  - kinematics/IK assets.
  - dataset playback.
- Checked architecture references in `README.md`, `docs/assets/README.md`,
  and release/media documentation.
- Inspected `docs/assets/system-architecture.png` metadata and searched for an
  editable source file. No Mermaid, SVG source, or diagram source file exists in
  the repository.
- Attempted local OCR/text extraction from the PNG; it did not produce usable
  text. The comparison therefore uses the README architecture block as the
  current diagram contract.

### Implementation Architecture Summary

- Algorithm machine:
  - Python user code, scripts, `FrankaEnv`, teleop devices, trajectory tools,
    kinematics/IK, camera ingestion, data collection, and dataset playback.
  - `RobotClient` uses a ZMQ DEALER command socket on port `5555` and a PULL
    state socket on port `5557`.
  - `GripperClient` uses a ZMQ DEALER command socket on port `5556`.
- Control machine:
  - `RobotServer` owns the `pylibfranka`/`aiofranka` robot connection and binds
    the command endpoint plus PUSH state stream.
  - `GripperServer` owns the `pylibfranka.Gripper` connection and runs gripper
    commands in a worker thread.
- Data collection:
  - `collect_episodes.py` combines `FrankaEnv`, teleop provider,
    `CameraManager`, `StateStreamRecorder`, and `DataCollector`.
  - `StateStreamRecorder` is the bridge that continuously samples robot state
    and latest camera frames while the collection loop sends actions.
- Planning/analysis:
  - Trajectory modules provide offline route planning and execution through
    `FrankaEnv`.
  - `IKSolver` uses bundled FR3v2 URDF/mesh assets through Pinocchio.
  - `scripts/play_dataset.py` is an offline dataset visualization entry point.

### Diagram Comparison

- The current architecture documentation is correct at the high level for the
  dual-machine no-ROS ZMQ design:
  - algorithm/GPU machine talks to a control/RT machine;
  - robot commands use port `5555`;
  - robot state stream uses port `5557`;
  - gripper commands use port `5556`;
  - data collection integrates robot state, actions, and RealSense images.
- The diagram/documentation is incomplete for the final high-value open-source
  presentation if it is meant to describe the whole project:
  - It should show `StateStreamRecorder`, because it is the key bridge between
    environment stepping, camera capture, and LeRobot writing.
  - It should either show or intentionally exclude `TrajectoryPlanner`,
    `WaypointStore`, `IKSolver`, dataset playback, and offline analysis.
  - It should clarify that `RobotClient.set()` is fire-and-forget/latest-wins on
    the command channel, while commands such as `connect`, `move`, `start`,
    `switch_controller`, and `get_state` are request/response style calls.
  - It should make the FCI/private robot network versus algorithm-to-control PC
    network distinction obvious enough for a new hardware user.
- Maintainability issue: `docs/assets/system-architecture.png` has no editable
  source file, so future architecture reviews cannot easily diff or regenerate
  the diagram.

### Findings

- No business code was changed in this review round.
- `todo.md` now tracks architecture follow-ups:
  - regenerate the architecture PNG with editable source;
  - decide whether the final diagram is minimal dual-machine control or full
    project architecture;
  - fix or document the `--gripper-mode none` behavior in
    `collect_episodes.py`;
  - clarify the `RobotClient.set()` semantics;
  - consider showing robot/gripper hardware-level coupling.
- Potential bug identified for a later approved code-change batch:
  `collect_episodes.py --gripper-mode none` disables the teleop gripper mode but
  still passes a gripper host into `FrankaEnv`, so no-gripper 6D actions can
  mismatch the environment's 7D action space.

### Done Criteria for This Round

- The real implementation architecture has been traced across control, gripper,
  environment, data, camera, trajectory, kinematics, teleop, and visualization
  modules.
- Architecture diagram/documentation gaps have been recorded as actionable
  follow-ups.
- No source behavior was changed without a separate user-approved code plan.

## 2026-04-30: README, Changelog, and Citation Release Pass

### Current Subtask

Finalize the release-facing `README.md`, `CHANGELOG.md`, and `CITATION.cff`
wording for the intended `v0.1.0` release.

### This Round's Method

- Checked `README.md`, `CHANGELOG.md`, `CITATION.cff`,
  `docs/community_submission.md`, and release checklist references for release
  date, version, demo media, architecture, and citation consistency.
- Updated `README.md` to:
  - mark the repository as a `v0.1.0` release candidate;
  - clarify command-channel versus state-stream architecture wording;
  - add `StateStreamRecorder` to the text architecture block;
  - clarify that `RobotClient.set()` is fire-and-forget/latest-command, while
    other robot commands use request/response semantics;
  - align the BibTeX example with `CITATION.cff`.
- Updated `CHANGELOG.md` to finalize `0.1.0` with release date `2026-04-30`
  and include release notes for hardware validation, packaging assets, redaction,
  generated artifact policy, and removal of the stale `collect_data` entry
  point.
- Updated `CITATION.cff` release date to `2026-04-30`.
- Updated `todo.md`, `acceptance.md`, and `docs/community_submission.md` to
  reflect the completed local release-doc pass.

### Validation

- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.
- `python -m pytest tests -q` passed with 56 tests and 5 warnings.
- `CITATION.cff` parsed with PyYAML and contains the required release metadata.
- `README.md`, `CHANGELOG.md`, and `CITATION.cff` have no remaining
  `Unreleased`, old `2026-04-27`, stale `author = {ArrebolBlack}`, or `TBD`
  markers.
- Known sensitive-value scan over README, changelog, citation, and docs found no
  matches for the previously identified lab IPs, hostnames, local paths, or
  camera serials.

### Remaining

- Decide whether to regenerate the architecture PNG with editable source before
  release, or ship the current PNG with the corrected README text.
- Decide whether the `--gripper-mode none` behavior must be fixed before
  `v0.1.0` or tracked as a post-release bug.
- Tag and publish `v0.1.0`, then update the Franka Community submission with
  the final GitHub Release URL.

## 2026-04-30: Updated Architecture Diagram Integrated

### Current Subtask

Integrate the updated architecture diagram into the release asset path and
record the diagram status.

### This Round's Method

- Checked the updated image asset supplied in `docs/assets/`.
- Replaced the README-linked asset path
  `docs/assets/system-architecture.png` with the updated diagram.
- Confirmed the final checked-in architecture image metadata:
  - PNG image.
  - `2752 x 1536`.
  - RGB color.
  - About `4.6M`.
- Kept the stable README path unchanged so existing docs continue to link to
  `docs/assets/system-architecture.png`.
- Updated `docs/assets/README.md`, `todo.md`, and `acceptance.md` to reflect
  the refreshed full-project architecture diagram.

### Validation

- `docs/assets/system-architecture.png` exists at the path referenced by
  `README.md`.
- The temporary Chinese-named architecture image file was folded into the stable
  release asset path and is no longer present as a duplicate untracked file.
- OCR/text validation could not be run because `tesseract` is not installed in
  the current environment.
- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.

### Remaining

- Add the editable source used to draw the architecture diagram if it is
  available.
- Review the remaining `--gripper-mode none` follow-up before release.

## 2026-04-30: Architecture Diagram v2 Replacement

### Current Subtask

Replace the release architecture diagram with the user-provided
`franka-control架构图2.png` asset.

### This Round's Method

- Located the new image at `docs/assets/franka-control架构图2.png`.
- Confirmed both the previous standard asset and the new image were PNG files
  with the same `2752 x 1536` RGB dimensions.
- Moved the new image into the stable README-linked path:
  `docs/assets/system-architecture.png`.
- Removed the duplicate temporary Chinese-named file by folding it into the
  standard release asset path.

### Validation

- `docs/assets/system-architecture.png` now points to the v2 architecture image.
- The README path remains stable and does not need to change.

## 2026-04-30: Release Continues with Gripper-None Bug Deferred

### Current Subtask

Continue the `v0.1.0` release path without changing the
`collect_episodes.py --gripper-mode none` behavior.

### This Round's Method

- Reviewed the `--gripper-mode none` issue and confirmed it is outside the
  validated release workflow, which uses the default binary gripper path.
- Deferred the bug to a post-release follow-up instead of changing hardware-facing
  data-collection behavior immediately before release.
- Confirmed commit/release identity before continuing:
  - `git config user.name` is `ArrebolBlack`.
  - `git config user.email` is `2078004110@qq.com`.
  - GitHub CLI is authenticated as `ArrebolBlack`.

### Remaining

- Run final release checks.
- Commit the release-readiness changes.
- Push `main`, tag `v0.1.0`, push the tag, and create the GitHub Release.
- Track the `--gripper-mode none` collection path as a post-release issue.

## 2026-04-30: Final Local Release Checks

### Current Subtask

Run the final local checks before committing and publishing `v0.1.0`.

### This Round's Method

- Kept the `--gripper-mode none` issue deferred and did not change data
  collection behavior.
- Ran the local release gate commands.
- Built a release wheel and inspected required bundled kinematics assets.
- Checked whether `v0.1.0` already exists locally or on GitHub.

### Validation

- `python -m pytest tests -q` passed with 56 tests and 5 warnings.
- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.
- `python -m ruff check franka_control scripts tests` passed.
- Important scripts passed `python -m py_compile`.
- CLI `--help` smoke tests passed for robot, gripper, teleop,
  `collect_episodes`, `collect_waypoints`, `run_trajectory`,
  `measure_latency`, camera listing, dataset player, and validation-info helper.
- Sensitive-value scan found no matches for the previously identified lab IPs,
  hostnames, local paths, or camera serials.
- Built wheel:
  `python -m pip wheel . -w /tmp/franka-control-release-wheel --no-deps`.
- Wheel contains required kinematics assets:
  - `franka_control/kinematics/assets/fr3v2.urdf`.
  - `franka_control/kinematics/assets/meshes/robots/fr3v2/visual/link0.dae`.
  - `franka_control/kinematics/assets/meshes/robots/fr3v2/collision/link0.stl`.
- Local tag `v0.1.0` does not exist yet.
- GitHub Release `v0.1.0` does not exist yet.
- Latest public GitHub Actions run on `origin/main` before this release commit
  is still green: run `25119439661`.

### Remaining

- Commit and push the release-readiness changes.
- Tag and publish `v0.1.0`.
- Create a GitHub Release and let CI run on the pushed commit/tag.

## 2026-04-30: README Demo Media Rendering Fix

### Current Subtask

Correctly use the release demo videos and screenshots in the README before
publishing `v0.1.0`.

### This Round's Method

- Paused the tag/release step after the user reported that demo media was not
  being used correctly in `README.md`.
- Reviewed the existing `README.md` media section and `docs/assets/` contents.
- Attempted to inspect/generate video thumbnails, but the current environment
  does not have `cv2`, `ffmpeg`, or `ffprobe` available.
- Updated `README.md` to show:
  - keyboard teleoperation MP4 with video controls and fallback link;
  - SpaceMouse teleoperation MP4 with video controls and fallback link;
  - dataset playback MP4 with video controls and fallback link;
  - trajectory and action-distribution screenshots as embedded images.

### Remaining

- Commit and push this README media fix before tagging `v0.1.0`.

### Validation

- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.
- GitHub Actions run `25139136138` for the previous release-readiness commit
  passed before this README media fix was committed.

## 2026-04-30: README Logo Integration

### Current Subtask

Add the user-provided `docs/assets/logo.png` to the README and assets index.

### This Round's Method

- Located `docs/assets/logo.png`.
- Confirmed image metadata: PNG, `1672 x 941`, RGB.
- Added the logo at the top of `README.md` as the first visual brand signal.
- Registered `logo.png` in `docs/assets/README.md`.
- Marked the optional logo item complete in `todo.md`.

### Remaining

- Commit and push the README logo update before tagging `v0.1.0`.

### Validation

- `python scripts/check_markdown_links.py` passed.
- `git diff --check` passed.
- `docs/assets/logo.png` is about `1.2M`.

## 2026-04-30: README GIF Demo Preview Integration

### Current Subtask

Use the newly available demo GIF previews correctly in the README.

### This Round's Method

- Found three demo preview GIFs in `docs/assets/`:
  - `keyboard-teleop-install-gear.gif`.
  - `spacemouse-teleop-pouring.gif`.
  - `dataset-player-fruit-basket.gif`.
- Confirmed their sizes and dimensions:
  - keyboard teleop GIF: about `1.9M`, `480 x 206`.
  - SpaceMouse teleop GIF: about `2.0M`, `480 x 206`.
  - dataset playback GIF: about `4.7M`, `480 x 270`.
- Updated `README.md` so the demo section uses inline GIF previews that link to
  the higher-quality MP4 files.
- Updated `docs/assets/README.md` to list the GIF preview assets.

### Remaining

- Run link/diff checks.
- Commit and push the README demo GIF update before tagging `v0.1.0`.
