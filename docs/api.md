# Python API

This page collects the primary Python APIs for embedding Franka Control in your
own research code.

## FrankaEnv

```python
import numpy as np
from franka_control.envs import FrankaEnv

env = FrankaEnv(
    robot_ip="192.168.0.100",
    gripper_host="192.168.0.100",
    action_mode="ee_delta",
    gripper_mode="binary",
)

obs, info = env.reset()

action = np.array([0.01, 0, 0, 0, 0, 0, 1.0], dtype=np.float32)
obs, reward, terminated, truncated, info = env.step(action)
print(info["applied_action"])

env.close()
```

Action modes:

| Mode | Robot action dimensions | Meaning |
|---|---:|---|
| `joint_abs` | 7 | absolute joint position |
| `joint_delta` | 7 | joint position increment |
| `ee_abs` | 6 | absolute EE pose: position + rotvec |
| `ee_delta` | 6 | EE pose increment: position + rotvec |

If a gripper is enabled, one gripper dimension is appended.

## DataCollector

`DataCollector` is a recorder only. It does not control the robot or cameras.

```python
from pathlib import Path
import numpy as np
from franka_control.data import CollectionConfig, DataCollector

config = CollectionConfig(
    repo_id="user/example",
    root=Path("data/example"),
    task_name="pick cube",
    robot_ip="192.168.0.100",
    gripper_host="192.168.0.100",
    control_mode="ee_delta",
    fps=60,
    use_videos=False,
    streaming_encoding=False,
)

collector = DataCollector(config)
collector.start_episode("pick cube")

obs = {
    "joint_pos": np.zeros(7, dtype=np.float32),
    "joint_vel": np.zeros(7, dtype=np.float32),
    "joint_torque": np.zeros(7, dtype=np.float32),
    "ee_pos": np.zeros(3, dtype=np.float32),
    "ee_quat": np.array([0, 0, 0, 1], dtype=np.float32),
    "gripper_width": np.array([0.08], dtype=np.float32),
}

collector.record_frame(obs, np.zeros(7, dtype=np.float32), images=None)
collector.end_episode(success=True)
collector.finalize()
```

Extra features:

```python
collector = DataCollector(
    config,
    extra_features={
        "observation.phase": {
            "dtype": "int32",
            "shape": (3,),
            "names": ["approach", "grasp", "place"],
        },
    },
)
```

## CameraManager

```python
from franka_control.cameras import CameraManager

cameras = CameraManager.from_yaml("config/cameras.yaml")
frames = cameras.read()
latest = cameras.read_latest()
rgb = frames["d435"]["rgb"]
cameras.close()
```

`read()` may block until a frame is available. `read_latest()` is non-blocking and
returns the most recent cached frame for each camera.

## FK/IK

```python
import numpy as np
from franka_control.kinematics import IKSolver

solver = IKSolver()
q = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])

T = solver.fk(q)
q_solution, converged = solver.ik(q, T)
```

## Trajectory Tools

```python
from franka_control.trajectory.planner import TrajectoryPlanner
from franka_control.trajectory.waypoints import WaypointStore

store = WaypointStore()
store.load("config/waypoints.yaml")

planner = TrajectoryPlanner()
route = store.get_route("pick_place")
```

For execution, prefer the CLI first:

```bash
python -m franka_control.scripts.run_trajectory \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --dry-run
```

