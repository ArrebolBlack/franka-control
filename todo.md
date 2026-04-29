# Task Breakdown and Current Status

This file tracks actionable work for the Franka Community readiness effort.
The detailed rationale is in `plan.md`; this file is the working checklist.

Status legend:

- `[x]` Done
- `[~]` In progress
- `[ ]` Not started
- `[!]` Blocked or needs external input

## Current State

- `[x]` English README added.
- `[x]` Chinese README preserved as `README.zh-CN.md`.
- `[x]` Docs folder started.
- `[x]` Apache-2.0 license added.
- `[x]` Citation file added.
- `[x]` Contributing and security docs added.
- `[x]` `plan.md` added.
- `[x]` Community-readiness documentation is expanded.
- `[x]` CI workflow is added locally.
- `[x]` Community-readiness batch is committed locally.
- `[x]` Community-readiness batch is pushed to `origin/main`.
- `[x]` GitHub Actions is green on `origin/main`.
- `[x]` GitHub Actions v6 upgrade completed and CI remains green.
- `[x]` GitHub About description and topics are set.
- `[x]` GitHub release-blocker milestone and issues are created.
- `[x]` GitHub issue `#1` README demo media is closed.
- `[x]` GitHub issue `#2` hardware validation is closed.
- `[x]` Hardware validation environment-info helper is added.
- `[x]` Hardware validation helper is covered by green CI.
- `[x]` RealSense camera listing helper is added.
- `[x]` Media capture runbook is added.
- `[x]` Release materials checklist is added.
- `[x]` Hardware validation matrix has real setup/environment values and
  functional workflow results.
- `[x]` README demo media assets are added.
- `[x]` Data-collection usability polish is implemented and CI is green.
- `[ ]` GitHub release is not created yet.
- `[ ]` Franka Community submission has not been sent yet.

## Confirmed Optimization Program

Confirmed on 2026-04-30. The next work is an open-source readiness and
repository-quality pass. Code changes require a file-level plan and user
approval before execution.

- `[x]` Confirm high-value open-source goal and Franka Community positioning.
- `[x]` Record collaboration and contributor identity rules in `CLAUDE.md`.
- `[x]` Audit repository structure, docs, tests, packaging, release blockers,
  local/generated files, and public-redaction risk.
- `[x]` Decide policy for untracked `demo/` and `test_output/` artifacts:
  commit curated public samples, publish as external release assets, or keep
  fully local and ignored.
- `[x]` Prepare and execute a code-change proposal for packaging URDF/mesh assets in source
  distributions and wheels.
- `[x]` Prepare and execute a cleanup proposal for deprecated or historical files such as
  `franka_control/scripts/collect_data.py` and ignored development notes.
- `[x]` Prepare and execute a test-coverage proposal for robot/env/trajectory/kinematics
  offline behavior without requiring hardware.
- `[x]` Confirm final architecture diagram still matches the implementation and
  update it only if needed.
- `[x]` Run final public redaction over docs, release notes, demo metadata, and
  generated artifacts.
- `[x]` Finalize README with architecture, teleop, data collection, dataset
  visualization, media links, and known limitations.
- `[x]` Optional: create or add a project logo only if it improves public
  presentation without delaying release.

## Architecture Review Follow-Ups

- `[x]` Update or regenerate `docs/assets/system-architecture.png`.
- `[ ]` Add an editable architecture source file if available, so future
  architecture changes are reviewable without reverse-engineering the PNG.
- `[x]` Decide diagram scope: final diagram should present the full project
  architecture, including the dual-machine ZMQ control path plus data
  collection, trajectory, kinematics, playback, and analysis tools.
- `[ ]` Post-release: fix or clarify `--gripper-mode none` in
  `franka_control/scripts/collect_episodes.py`; current code still creates a
  gripper-backed `FrankaEnv`, which can make 6D no-gripper actions mismatch the
  environment's expected 7D action space. This is not blocking `v0.1.0` because
  the validated release workflow uses the default binary gripper path.
- `[x]` Clarify in architecture/docs that `RobotClient.set()` is a
  fire-and-forget latest-wins command on the ZMQ command channel, not a normal
  request/response RPC like `connect`, `move`, or `get_state`.
- `[ ]` Consider showing the Franka hardware-level coupling between robot and
  gripper operations, because blocking `pylibfranka` gripper calls can pause
  robot-side progress even though the gripper service has its own worker
  thread.

## Audit-Driven Change Proposals

These are proposed work items only. Code or structural changes still require
user approval before implementation.

- `[x]` Packaging assets:
  - Candidate files: `pyproject.toml`, optional `MANIFEST.in`, optional
    packaging test.
  - Goal: built wheels and source distributions must include
    `franka_control/kinematics/assets/fr3v2.urdf` and required mesh files.
- `[x]` Legacy data collection entry point:
  - Candidate file: `franka_control/scripts/collect_data.py`.
  - Goal: remove it, mark it deprecated, or redirect users to
    `franka_control.scripts.collect_episodes`.
- `[x]` Generated artifact policy:
  - Candidate files: `.gitignore`, docs under `docs/assets/` or release docs.
  - Goal: prevent `demo/*/meta` and `test_output/*/meta` files from appearing
    as accidental untracked release material, while preserving deliberate media.
- `[x]` Public redaction:
  - Candidate files: `docs/hardware_validation.md`,
    `docs/community_submission.md`, `docs/release_materials_checklist.md`.
  - Goal: replace private hostnames, local paths, real lab IPs, and camera
    serials with safe examples or anonymized values before release.
- `[x]` Offline test coverage:
  - Candidate files: tests for packaging, env action clipping/splitting,
    trajectory route splitting/planning validation, state-recorder conversion,
    and IK asset availability.
  - Goal: cover high-risk non-hardware behavior without requiring an FR3.

## Phase 1: Documentation Foundation

- `[x]` Add English `README.md`.
- `[x]` Move or preserve Chinese README.
- `[x]` Add `docs/README.md`.
- `[x]` Add `docs/quickstart.md`.
- `[x]` Add `docs/data_collection.md`.
- `[x]` Add `docs/api.md`.
- `[x]` Add `docs/ros_comparison.md`.
- `[x]` Add `docs/assets/README.md`.
- `[x]` Add `LICENSE`.
- `[x]` Add `CITATION.cff`.
- `[x]` Add `CONTRIBUTING.md`.
- `[x]` Add `SECURITY.md`.
- `[x]` Add `plan.md`.
- `[x]` Add `goal.md`.
- `[x]` Add `todo.md`.
- `[x]` Add `progress.md`.
- `[x]` Add `acceptance.md`.

## Phase 2: Missing Community-Readiness Docs

- `[x]` Add `docs/troubleshooting.md`.
- `[x]` Add `docs/hardware_validation.md`.
- `[x]` Add `ROADMAP.md`.
- `[x]` Add `CHANGELOG.md`.
- `[x]` Add `docs/community_submission.md`.
- `[x]` Link new docs from README and `docs/README.md`.

## Phase 3: CI and Quality Gates

- `[x]` Add `.github/workflows/ci.yml`.
- `[x]` Configure pytest in CI.
- `[x]` Configure Python compile checks in CI.
- `[x]` Configure CLI `--help` smoke tests in CI.
- `[x]` Add Markdown relative-link checker.
- `[x]` Add limited `ruff` configuration.
- `[x]` Add CI badge to README after workflow is stable.
- `[x]` Upgrade GitHub Actions to Node.js 24-compatible major versions.

## Phase 4: GitHub Collaboration Files

- `[x]` Add `.github/ISSUE_TEMPLATE/bug_report.yml`.
- `[x]` Add `.github/ISSUE_TEMPLATE/hardware_issue.yml`.
- `[x]` Add `.github/ISSUE_TEMPLATE/feature_request.yml`.
- `[x]` Add `.github/pull_request_template.md`.
- `[x]` Add labels if maintaining manually on GitHub:
  - `hardware`
  - `safety`
  - `data`
  - `docs`
  - `good first issue`
  - `needs validation`

## Phase 5: Media and Visual Proof

- `[x]` Create `docs/assets/system-architecture.png`.
- `[x]` Add media capture runbook.
- `[x]` Add release materials checklist for hardware/media collection.
- `[x]` Add `docs/assets/keyboard-teleop-install-gear.mp4`.
- `[x]` Add `docs/assets/spacemouse-teleop-pouring.mp4`.
- `[x]` Add `docs/assets/dataset-player-fruit-basket.mp4`.
- `[x]` Add `docs/assets/trajectory-analysis.png`.
- `[x]` Add `docs/assets/action-distribution.png`.
- `[x]` Update README to link final assets.

## Phase 6: Hardware Validation

- `[x]` Add helper to collect environment/package versions for validation.
- `[x]` Fill robot model and Franka system version.
- `[x]` Fill network addresses and default service ports.
- `[x]` Fill control PC OS and kernel.
- `[x]` Fill algorithm PC OS.
- `[x]` Fill Python and dependency versions.
- `[x]` Record RealSense camera models, serials, firmware, and USB type.
- `[x]` Record keyboard and SpaceMouse device details.
- `[x]` Validate `RobotServer`.
- `[x]` Validate `GripperServer`.
- `[x]` Validate latency measurement.
- `[x]` Validate keyboard teleop.
- `[x]` Validate SpaceMouse teleop.
- `[x]` Validate waypoint collection.
- `[x]` Validate trajectory dry-run.
- `[x]` Validate safe trajectory execution.
- `[x]` Validate RealSense camera preview.
- `[x]` Validate data collection with cameras.
- `[x]` Validate data collection with `--no-camera`.
- `[x]` Validate dataset player.
- `[x]` Validate blocking gripper operations do not freeze recorded camera frames.
- `[x]` Add helper to list RealSense serials and generate camera YAML snippets.

## Phase 7: Release

- `[x]` Finalize `CHANGELOG.md`.
- `[x]` Final public redaction pass over docs and release notes.
- `[x]` Align `CITATION.cff` with the actual release date.
- `[x]` Create GitHub milestone `v0.1.0`.
- `[x]` Create release-blocker issues for media, hardware validation, release,
  and Franka Community submission.
- `[x]` Confirm all tests pass.
- `[x]` Confirm all docs links pass.
- `[x]` Confirm hardware validation table is filled.
- `[ ]` Tag `v0.1.0`.
- `[ ]` Push tag.
- `[ ]` Create GitHub Release.
- `[ ]` Attach or link demo media.

## Phase 8: Franka Community Submission

- `[ ]` Finalize short project description.
- `[ ]` Finalize submission email.
- `[ ]` Include repository URL.
- `[ ]` Include release URL.
- `[ ]` Include demo URL.
- `[ ]` Propose categories:
  - Robot Control & Motion Planning.
  - Learning Environments and Datasets.
- `[ ]` Send to `research@franka.de`.

## Immediate Next Task

Recommended next implementation batch:

1. Add an editable architecture source file if the source used to draw the PNG
   is available.
2. Complete issue `#3`: tag and publish the `v0.1.0` GitHub release.
3. Complete issue `#4`: finalize Franka Community submission after release.
4. Post-release: fix or document the `--gripper-mode none` collection path.
