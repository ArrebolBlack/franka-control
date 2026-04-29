# Hardware Validation

This page records real hardware setups that have been tested with Franka
Control. Do not mark an item as validated from simulation or source inspection
alone.

## Tested Setup

| Item | Tested Value | Status | Notes |
|---|---|---|---|
| Robot | Franka Research 3, Arm3Rv2 | Recorded, pending workflow validation | Provided from the real FR3 setup |
| Franka system version | Control `5.9.2`; system image `5.9.2` | Recorded, pending workflow validation | Provided from Franka system UI |
| Franka Hand | Franka Hand, default configuration | Recorded, pending gripper validation | Homing/open/close still need functional validation |
| Control PC OS | Ubuntu 24.04.4 LTS | Recorded | Host: `haoce-HP-Pro-Tower-ZHAN-99-G9-Desktop-PC` |
| Control PC kernel | `6.8.1-1046-realtime` PREEMPT_RT | Recorded | Full string: `Linux haoce-HP-Pro-Tower-ZHAN-99-G9-Desktop-PC 6.8.1-1046-realtime #47-Ubuntu SMP PREEMPT_RT Tue Mar 24 22:17:59 UTC 2026 x86_64 x86_64 x86_64 GNU/Linux` |
| Algorithm PC OS | Ubuntu 24.04.4 LTS | Recorded | Host: `yjq-ROG5090` |
| Python | Control PC: `3.11.15`; algorithm PC: `3.12.13` | Recorded, environment alignment recommended | CI targets Python 3.12; release target is one consistent control/algorithm environment where practical |
| RealSense cameras | Intel RealSense D405 `352122274606`; Intel RealSense D435 `138422075015` | Detected on algorithm PC, preview pending | `config/cameras.yaml` confirmed by operator |
| Teleop devices | Standard keyboard; 3Dconnexion SpaceMouse Compact `256f:c635` | Device recorded, motion validation pending | SpaceMouse permissions reported OK |
| Control modes | TBD | Pending validation | Example: `ee_delta`, `joint_delta`, `joint_abs` |
| Data collection FPS | TBD | Pending validation | Example: 30 or 60 |
| Robot RPC port | `5555` default | Confirmed from source | `franka_control/robot/robot_server.py` `DEFAULT_CMD_PORT` |
| Gripper RPC port | `5556` default | Confirmed from source | `franka_control/gripper/gripper_server.py` `DEFAULT_CMD_PORT`; client scripts default to `5556` |
| State stream port | `5557` default | Confirmed from source | `franka_control/robot/robot_server.py` `DEFAULT_STATE_STREAM_PORT` |

## Network and Services

| Item | Value | Notes |
|---|---|---|
| Franka FCI IP | `172.16.0.2` | Used only by the control PC when starting `RobotServer` or `GripperServer` |
| Control PC IP | `10.100.79.71` | Algorithm PC connects to this address as `--robot-ip` / `--gripper-host` |
| Algorithm PC IP | `10.100.74.202` | `172.17.0.1` was also reported by `hostname -I`; this is a Docker bridge address, not the robot-control network address |
| Robot service command | `python -m franka_control.robot --fci-ip 172.16.0.2` | Uses default RPC port `5555` and state stream port `5557` unless overridden |
| Gripper service command | `python -m franka_control.gripper --robot-ip 172.16.0.2` | Uses default RPC port `5556` unless overridden |
| Gripper host from algorithm PC | Usually `10.100.79.71` | The gripper service normally runs on the control PC |
| Camera config | `config/cameras.yaml` confirmed | Exact camera preview still needs functional validation |

Review these addresses before public release if lab-local network details should
be redacted from the final public hardware page.

## Control PC Environment

Collected at UTC `2026-04-29T10:38:48+00:00`.

| Item | Value |
|---|---|
| Hostname | `haoce-HP-Pro-Tower-ZHAN-99-G9-Desktop-PC` |
| Platform | `Linux-6.8.1-1046-realtime-x86_64-with-glibc2.39` |
| OS | `Linux 6.8.1-1046-realtime` |
| Kernel | `6.8.1-1046-realtime` |
| Architecture | `x86_64` |
| Python | `3.11.15 (main, Mar 11 2026, 17:20:07) [GCC 14.3.0]` |
| Python executable | `/home/haoce/miniconda3/envs/franka/bin/python` |
| Git commit | `99a8d9c` |

Package versions:

| Package | Version |
|---|---|
| `franka-control` | `not installed` |
| `numpy` | `2.2.6` |
| `scipy` | `1.17.1` |
| `gymnasium` | `1.2.3` |
| `pyzmq` | `27.1.0` |
| `msgpack` | `1.1.2` |
| `torch` | `2.10.0` |
| `torchvision` | `0.25.0` |
| `lerobot` | `0.4.4` |
| `pyrealsense2` | `2.57.7.10387` |
| `opencv-python` | `not installed` |
| `matplotlib` | `3.10.8` |
| `pyspacemouse` | `2.0.0` |
| `pynput` | `1.8.1` |
| `pin` | `not installed` |
| `toppra` | `0.6.3` |
| `pylibfranka` | `0.21.1` |
| `aiofranka` | `0.3.0` |

## Algorithm PC Environment

Collected at UTC `2026-04-29T10:41:47+00:00`.

| Item | Value |
|---|---|
| Hostname | `yjq-ROG5090` |
| Platform | `Linux-6.17.0-22-generic-x86_64-with-glibc2.39` |
| OS | `Linux 6.17.0-22-generic` |
| Kernel | `6.17.0-22-generic` |
| Architecture | `x86_64` |
| Python | `3.12.13, packaged by Anaconda, Inc., (main, Mar 19 2026, 20:20:58) [GCC 14.3.0]` |
| Python executable | `/home/yjq/.conda/envs/franka/bin/python` |
| Git commit | `63b029c` |

Package versions:

| Package | Version |
|---|---|
| `franka-control` | `0.1.0` |
| `numpy` | `2.4.4` |
| `scipy` | `1.17.1` |
| `gymnasium` | `1.3.0` |
| `pyzmq` | `27.1.0` |
| `msgpack` | `1.1.2` |
| `torch` | `2.10.0` |
| `torchvision` | `0.25.0` |
| `lerobot` | `0.5.1` |
| `pyrealsense2` | `2.57.7.10387` |
| `opencv-python` | `4.13.0.92` |
| `matplotlib` | `3.10.9` |
| `pyspacemouse` | `2.0.0` |
| `pynput` | `1.8.1` |
| `pin` | `3.9.0` |
| `toppra` | `0.6.3` |
| `pylibfranka` | `not installed` |
| `aiofranka` | `not installed` |

Detected RealSense devices:

| Device | Name | Serial | Firmware | USB |
|---|---|---|---|---|
| 1 | Intel RealSense D405 | `352122274606` | `5.15.1.55` | `3.2` |
| 2 | Intel RealSense D435 | `138422075015` | `5.12.7.150` | `3.2` |

The two collected environment outputs report different git commits
(`99a8d9c` on the control PC and `63b029c` on the algorithm PC). Before final
release, rerun `scripts/collect_validation_info.py` on both machines after they
are synchronized to the same commit.

## Offline Validation

These checks do not require robot hardware:

| Check | Command | Status |
|---|---|---|
| Unit tests | `python -m pytest tests -q` | Passing locally |
| Important script compile | `python -m py_compile franka_control/scripts/collect_episodes.py scripts/play_dataset.py` | Passing locally |
| CLI help smoke tests | See `acceptance.md` | Passing locally, pending GitHub CI |
| Markdown relative links | `python scripts/check_markdown_links.py` | Passing locally, pending GitHub CI |
| Ruff correctness checks | `python -m ruff check franka_control scripts tests` | Passing locally, pending GitHub CI |

Collect environment details on each machine and paste the relevant values into
the table below:

```bash
python scripts/collect_validation_info.py --format markdown
```

On the algorithm PC, optionally include connected RealSense devices:

```bash
python scripts/collect_validation_info.py --format markdown --probe-realsense
```

This helper does not connect to the Franka robot.

## Hardware Checklist

Record date, operator, and notes before marking any item complete.

| Validation Item | Status | Date | Notes |
|---|---|---|---|
| RobotServer starts | `[ ]` | TBD | Use `python -m franka_control.robot --fci-ip 172.16.0.2` |
| GripperServer starts | `[ ]` | TBD | Use `python -m franka_control.gripper --robot-ip 172.16.0.2` |
| Latency measurement works | `[ ]` | TBD | Run from algorithm PC |
| Keyboard teleop works at low speed | `[ ]` | TBD | Start with low `--action-scale-*` |
| SpaceMouse teleop works at low speed | `[ ]` | TBD | Device: 3Dconnexion SpaceMouse Compact; permissions reported OK |
| Waypoint collection works | `[ ]` | TBD | Save and reload `config/waypoints.yaml` |
| Trajectory dry-run works | `[ ]` | TBD | No robot connection required |
| Safe trajectory execution works | `[ ]` | TBD | Use low velocity and acceleration scales |
| Camera preview works | `[ ]` | TBD | D405 and D435 detected; `config/cameras.yaml` confirmed |
| Data collection with cameras works | `[ ]` | TBD | Confirm image/state alignment |
| Data collection with `--no-camera` works | `[ ]` | TBD | Isolates robot and dataset path |
| Dataset player works | `[ ]` | TBD | Requires OpenCV GUI support |
| Blocking gripper calls do not freeze recorded camera frames | `[ ]` | TBD | Compare frame timestamps during grasp |

## Validation Commands

Control PC:

```bash
python -m franka_control.robot \
    --fci-ip 172.16.0.2 \
    --port 5555 \
    --state-stream-port 5557 \
    --poll-hz 1000
```

Control PC, second terminal:

```bash
python -m franka_control.gripper \
    --robot-ip 172.16.0.2 \
    --port 5556 \
    --poll-hz 50
```

Algorithm PC:

```bash
python -m franka_control.scripts.measure_latency \
    --robot-ip 10.100.79.71 \
    -n 100
```

Low-speed keyboard teleop:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 10.100.79.71 \
    --gripper-host 10.100.79.71 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

State-only one-episode dataset:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 10.100.79.71 \
    --gripper-host 10.100.79.71 \
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
