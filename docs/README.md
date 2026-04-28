# Documentation

This directory contains practical documentation for installing, running, and
extending Franka Control.

## Start Here

| Page | Purpose |
|---|---|
| [Quick Start](quickstart.md) | Fresh install, service startup, teleoperation, and a first dataset |
| [Data Collection](data_collection.md) | LeRobot schema, camera setup, collection commands, and controls |
| [Python API](api.md) | `FrankaEnv`, `DataCollector`, cameras, FK/IK, and trajectory examples |
| [No-ROS Design and ROS Comparison](ros_comparison.md) | How this project relates to ROS, `franka_ros`, `libfranka`, and LeRobot |
| [Troubleshooting](troubleshooting.md) | Common network, device, GUI, dataset, and safety problems |
| [Hardware Validation](hardware_validation.md) | Real tested setup matrix and validation checklist |
| [Community Submission](community_submission.md) | Franka Community description and email draft |
| [Media Assets](assets/README.md) | Reserved screenshot and diagram filenames for the README |
| [Roadmap](../ROADMAP.md) | Planned release direction and non-goals |
| [Changelog](../CHANGELOG.md) | User-facing release notes |

## Existing Design Notes

These files are lower-level development notes and may be more implementation-oriented:

| Page | Topic |
|---|---|
| [Environment Design](env_design.md) | `FrankaEnv` design details |
| [Implementation Plan](implementation_plan.md) | Historical implementation notes |
| [Phase 4 Plan Draft](phase4_plan_draft.md) | Historical phase planning |

## Documentation Policy

Keep user-facing commands synchronized with the actual CLI `--help` output. If a
script argument changes, update the README and the relevant docs page in the same
change. Hardware-facing changes also need safety notes and, when validated, an
update to [Hardware Validation](hardware_validation.md).
