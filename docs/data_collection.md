# Data Collection

The data collection pipeline records synchronized robot state, actions, task text,
success annotations, and optional camera streams into LeRobot v3 format.

## Components

| Component | Responsibility |
|---|---|
| `FrankaEnv` | Executes actions and returns observations |
| `CameraManager` | Reads RealSense RGB frames |
| `StateStreamRecorder` | Background robot state and camera recorder |
| `DataCollector` | Writes LeRobot frames and episodes |
| `collect_episodes.py` | End-user teleoperation collection script |
| `scripts/play_dataset.py` | Playback and quality inspection |

## Dataset Schema

Default features:

| Key | Shape | Description |
|---|---:|---|
| `observation.state` | `(8,)` | `q0..q6 + gripper_width` |
| `observation.joint_vel` | `(7,)` | Joint velocity |
| `observation.ee_pose` | `(7,)` | `x,y,z,qx,qy,qz,qw` |
| `observation.effort` | `(7,)` | Joint torque |
| `action` | `(8,)` or `(7,)` | Control command after clipping |
| `observation.images.<camera>` | `(H,W,3)` | RGB frame |
| `task` | string | Natural language instruction |

Action shape:

| Control mode | Action |
|---|---|
| `joint_abs` | `[q0..q6, gripper]` |
| `joint_delta` | `[dq0..dq6, gripper]` |
| `ee_abs` | `[x,y,z,rx,ry,rz,gripper]` |
| `ee_delta` | `[dx,dy,dz,drx,dry,drz,gripper]` |

The end-effector orientation observation is quaternion `qx,qy,qz,qw`.
The end-effector action rotation is a rotation vector.

## Camera Configuration

`config/cameras.yaml`:

```yaml
d435:
  serial: "138422075015"
  resolution: [640, 480]
  fps: 60
  enable_depth: false

d405:
  serial: "352122274606"
  resolution: [640, 480]
  fps: 60
  enable_depth: false
```

Both `enable_depth` and `depth` are accepted by `CameraManager`. The standard
collector currently records RGB images.

## Collect Episodes

SpaceMouse:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_pick \
    --root data/franka_pick \
    --task-name "pick red cube" \
    --device spacemouse \
    --control-mode ee_delta \
    --fps 60 \
    --num-episodes 50 \
    --cameras config/cameras.yaml
```

Keyboard:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_pick \
    --root data/franka_pick \
    --task-name "pick red cube" \
    --device keyboard \
    --control-mode ee_delta \
    --fps 30 \
    --num-episodes 10
```

Resume:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_pick \
    --root data/franka_pick \
    --resume \
    --num-episodes 20
```

Headless:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_headless \
    --root data/franka_headless \
    --display off
```

## Interaction

SpaceMouse mode:

| Input | Effect |
|---|---|
| SpaceMouse | 6-DoF motion |
| Left button | close gripper |
| Right button | open gripper |
| `s` | start recording |
| `e` | end episode and ask success/failure |
| `f` | discard / skip |
| `q` | quit |

Keyboard mode:

| Input | Effect |
|---|---|
| `W/S A/D R/F` | translation |
| `Q/E Z/X C/V` | rotation |
| `Space` | close gripper |
| `Enter` | open gripper |
| `Shift` | slow mode |
| `s` | start recording |
| `Esc` | end episode |

## Notes

- `StateStreamRecorder` reads robot state and camera frames in a background thread.
- Blocking gripper calls therefore do not freeze recorded camera frames.
- Success/failure is stored in `meta/episode_annotations.json`.
- Failed episodes are discarded by default unless `--save-failure` is set.

