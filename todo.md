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
- `[~]` Hardware validation matrix exists but real tested values are not filled yet.
- `[ ]` Real screenshots/GIFs are not added yet.
- `[ ]` GitHub release is not created yet.
- `[ ]` Franka Community submission has not been sent yet.

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
- `[ ]` Add labels if maintaining manually on GitHub:
  - `hardware`
  - `safety`
  - `data`
  - `docs`
  - `good first issue`
  - `needs validation`

## Phase 5: Media and Visual Proof

- `[x]` Create `docs/assets/system-architecture.png`.
- `[ ]` Record `docs/assets/teleop-preview.gif`.
- `[ ]` Record `docs/assets/data-collection-preview.gif`.
- `[ ]` Capture `docs/assets/dataset-player.png`.
- `[ ]` Capture `docs/assets/trajectory-analysis.png`.
- `[ ]` Update README to show final assets.

## Phase 6: Hardware Validation

- `[ ]` Fill robot model and Franka system version.
- `[ ]` Fill control PC OS and kernel.
- `[ ]` Fill algorithm PC OS.
- `[ ]` Fill Python and dependency versions.
- `[ ]` Validate `RobotServer`.
- `[ ]` Validate `GripperServer`.
- `[ ]` Validate latency measurement.
- `[ ]` Validate keyboard teleop.
- `[ ]` Validate SpaceMouse teleop.
- `[ ]` Validate waypoint collection.
- `[ ]` Validate trajectory dry-run.
- `[ ]` Validate safe trajectory execution.
- `[ ]` Validate RealSense camera preview.
- `[ ]` Validate data collection with cameras.
- `[ ]` Validate data collection with `--no-camera`.
- `[ ]` Validate dataset player.
- `[ ]` Validate blocking gripper operations do not freeze recorded camera frames.

## Phase 7: Release

- `[ ]` Finalize `CHANGELOG.md`.
- `[ ]` Confirm all tests pass.
- `[ ]` Confirm all docs links pass.
- `[ ]` Confirm hardware validation table is filled.
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

1. Capture final README media assets:
   - `docs/assets/teleop-preview.gif`
   - `docs/assets/data-collection-preview.gif`
   - `docs/assets/dataset-player.png`
   - `docs/assets/trajectory-analysis.png`
2. Fill `docs/hardware_validation.md` with real tested FR3 values.
3. Finalize `CHANGELOG.md` for `v0.1.0`.
4. Create the `v0.1.0` release after media and hardware validation are ready.
