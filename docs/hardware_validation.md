# Hardware Validation

This page records real hardware setups that have been tested with Franka
Control. Do not mark an item as validated from simulation or source inspection
alone.

## Tested Setup

| Item | Tested Value | Status | Notes |
|---|---|---|---|
| Robot | Franka Research 3 | Pending validation | Fill after real setup test |
| Franka system version | TBD | Pending validation | Record exact version from Desk or robot UI |
| Control PC OS | TBD | Pending validation | Example: Ubuntu 22.04 LTS |
| Control PC kernel | TBD | Pending validation | Record PREEMPT_RT version if used |
| Algorithm PC OS | TBD | Pending validation | Example: Ubuntu 22.04/24.04 |
| Python | 3.12 target, local tests also pass on 3.13 | Partial offline validation | CI targets 3.12 |
| RealSense cameras | TBD | Pending validation | Example: D435, D405 |
| Teleop devices | TBD | Pending validation | Example: keyboard, SpaceMouse Wireless |
| Control modes | TBD | Pending validation | Example: `ee_delta`, `joint_delta`, `joint_abs` |
| Data collection FPS | TBD | Pending validation | Example: 30 or 60 |
| Robot RPC port | `5555` default | Pending validation | Override only if needed |
| Gripper RPC port | `5556` default | Pending validation | Override only if needed |
| State stream port | `5557` default | Pending validation | Override only if needed |

## Offline Validation

These checks do not require robot hardware:

| Check | Command | Status |
|---|---|---|
| Unit tests | `python -m pytest tests -q` | Passing locally |
| Important script compile | `python -m py_compile franka_control/scripts/collect_episodes.py scripts/play_dataset.py` | Passing locally |
| CLI help smoke tests | See `acceptance.md` | Passing locally, pending GitHub CI |
| Markdown relative links | `python scripts/check_markdown_links.py` | Passing locally, pending GitHub CI |
| Ruff correctness checks | `python -m ruff check franka_control scripts tests` | Passing locally, pending GitHub CI |

## Hardware Checklist

Record date, operator, and notes before marking any item complete.

| Validation Item | Status | Date | Notes |
|---|---|---|---|
| RobotServer starts | `[ ]` | TBD | Use `python -m franka_control.robot --fci-ip <FCI_IP>` |
| GripperServer starts | `[ ]` | TBD | Use `python -m franka_control.gripper --robot-ip <FCI_IP>` |
| Latency measurement works | `[ ]` | TBD | Run from algorithm PC |
| Keyboard teleop works at low speed | `[ ]` | TBD | Start with low `--action-scale-*` |
| SpaceMouse teleop works at low speed | `[ ]` | TBD | Confirm HID permissions first |
| Waypoint collection works | `[ ]` | TBD | Save and reload `config/waypoints.yaml` |
| Trajectory dry-run works | `[ ]` | TBD | No robot connection required |
| Safe trajectory execution works | `[ ]` | TBD | Use low velocity and acceleration scales |
| Camera preview works | `[ ]` | TBD | Verify all configured serial numbers |
| Data collection with cameras works | `[ ]` | TBD | Confirm image/state alignment |
| Data collection with `--no-camera` works | `[ ]` | TBD | Isolates robot and dataset path |
| Dataset player works | `[ ]` | TBD | Requires OpenCV GUI support |
| Blocking gripper calls do not freeze recorded camera frames | `[ ]` | TBD | Compare frame timestamps during grasp |

## Validation Commands

Control PC:

```bash
python -m franka_control.robot \
    --fci-ip 192.168.0.2 \
    --port 5555 \
    --state-stream-port 5557 \
    --poll-hz 1000
```

Control PC, second terminal:

```bash
python -m franka_control.gripper \
    --robot-ip 192.168.0.2 \
    --port 5556 \
    --poll-hz 50
```

Algorithm PC:

```bash
python -m franka_control.scripts.measure_latency \
    --robot-ip 192.168.0.100 \
    -n 100
```

Low-speed keyboard teleop:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

State-only one-episode dataset:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/state_only \
    --root data/state_only \
    --task-name "state only validation" \
    --device keyboard \
    --control-mode ee_delta \
    --fps 30 \
    --num-episodes 1 \
    --no-camera \
    --display off
```

## Notes Policy

- Record failed validation honestly instead of deleting it.
- Include exact commands and logs for failures.
- Include whether the robot moved and whether emergency stop was needed.
- Do not tag a release as hardware validated until this page is filled with real
  tested values.
