# Franka Control

[English README](README.md)

Franka Research 3 双机控制、遥操作、轨迹执行和 LeRobot 数据采集工具库。

这个仓库的目标是把真实 FR3 采集流程做成一套可复现 pipeline：

1. 控制机连接 Franka FCI 和夹爪，运行机器人/夹爪服务。
2. 算法机通过网络连接控制机，运行遥操作、轨迹、相机和数据采集脚本。
3. 数据以 LeRobot v3 格式保存，可继续 resume、回放、截图、分析 action/轨迹。

本文按“完全新手从零开始”的顺序写：先理解架构，再安装环境，再启动服务，最后使用每个功能。

## 0. 安全提醒

真实机械臂有危险。首次运行任何真机命令前，请确认：

- Franka Desk 可访问，机器人处于可随时急停的安全环境。
- 机械臂周围没有人、障碍物、松动物体。
- 先用低速度、短距离、`--time-scale 3.0` 或更慢速度验证。
- 不确定 action/waypoint/trajectory 是否安全时，不要执行真机运动。

## 1. 整体架构

本项目采用双机架构。

```text
算法机 / GPU 机                                      控制机 / RT kernel
运行本仓库 Python 脚本                               连接 Franka FCI
──────────────────────────────                      ──────────────────────────────
FrankaEnv / teleop / collect                         RobotServer :5555
RobotClient ───────────── ZMQ TCP ─────────────────▶ aiofranka / Franka controller
状态流 PULL ◀──────────── :5557 ──────────────────── 1kHz state stream

GripperClient ─────────── :5556 ───────────────────▶ GripperServer / pylibfranka

CameraManager
RealSense cameras

LeRobotDataset
data/, videos/, meta/
```

### IP 和端口

| 名称 | 含义 | 典型值 | 用在哪里 |
|---|---|---:|---|
| `FCI IP` / `--fci-ip` | Franka 机器人本体的 FCI 地址 | `192.168.0.2` | 只在控制机启动 `RobotServer` 时使用 |
| `控制机 IP` / `--robot-ip` | 算法机访问控制机的地址 | `192.168.0.100` | 算法机所有脚本使用 |
| `--gripper-host` | 夹爪服务地址 | 默认等于 `--robot-ip` | 算法机连接 GripperServer |
| `5555` | RobotServer RPC 端口 | 固定默认 | `RobotClient` |
| `5556` | GripperServer RPC 端口 | 固定默认 | `GripperClient` |
| `5557` | RobotServer 状态流端口 | 固定默认 | `RobotClient.state` |

最常见错误是把 `--robot-ip` 写成 Franka FCI IP。算法机脚本里的 `--robot-ip` 应该是控制机 IP。

## 2. 功能总览

| 功能 | 主要代码 | 运行位置 | 入口命令 |
|---|---|---|---|
| RobotServer | `franka_control/robot/robot_server.py` | 控制机 | `python -m franka_control.robot` |
| GripperServer | `franka_control/gripper/gripper_server.py` | 控制机 | `python -m franka_control.gripper` |
| Gym 环境 | `franka_control/envs/franka_env.py` | 算法机 | Python API |
| SpaceMouse/键盘遥操作 | `franka_control/scripts/teleop.py` | 算法机 | `python -m franka_control.scripts.teleop` |
| Waypoint 采集 | `franka_control/scripts/collect_waypoints.py` | 算法机 | `python -m franka_control.scripts.collect_waypoints` |
| TOPPRA 轨迹执行 | `franka_control/scripts/run_trajectory.py` | 算法机 | `python -m franka_control.scripts.run_trajectory` |
| 多 episode 数据采集 | `franka_control/scripts/collect_episodes.py` | 算法机 | `python -m franka_control.scripts.collect_episodes` |
| 数据集播放器 | `scripts/play_dataset.py` | 算法机 | `python scripts/play_dataset.py` |
| RealSense 多相机 | `franka_control/cameras/camera_manager.py` | 算法机 | Python API / 采集脚本 |
| LeRobot 记录器 | `franka_control/data/collector.py` | 算法机 | Python API / 采集脚本 |
| 后台状态/相机录制 | `franka_control/data/state_recorder.py` | 算法机 | `collect_episodes.py` 内部使用 |
| FK/IK | `franka_control/kinematics/ik_solver.py` | 任意机器 | Python API |
| FK/IK 验证 | `franka_control/kinematics/verify_fk.py`, `verify_ik.py` | 算法机 | `python -m franka_control.kinematics.verify_fk` |
| 延迟测量 | `franka_control/scripts/measure_latency.py` | 算法机 | `python -m franka_control.scripts.measure_latency` |
| 旧版采集脚本 | `franka_control/scripts/collect_data.py` | 算法机 | 不推荐，保留兼容 |

## 3. 目录结构

```text
franka-control/
├── pyproject.toml                 # Python 包依赖和可编辑安装配置
├── requirements.txt               # pip requirements 形式的依赖清单
├── config/
│   ├── cameras.yaml               # RealSense 相机配置
│   └── waypoints.yaml             # 示例 waypoint / route 配置
├── scripts/
│   └── play_dataset.py            # LeRobot 数据集播放器
├── tests/
│   ├── test_data_collection.py
│   ├── test_gripper.py
│   └── test_keyboard_teleop.py
└── franka_control/
    ├── robot/                     # RobotServer / RobotClient
    ├── gripper/                   # GripperServer / GripperClient
    ├── envs/                      # FrankaEnv
    ├── teleop/                    # SpaceMouseTeleop / KeyboardTeleop
    ├── cameras/                   # CameraManager
    ├── data/                      # DataCollector / features / recorder
    ├── trajectory/                # waypoint / TOPPRA planner / executor
    ├── kinematics/                # Pinocchio FK/IK
    └── scripts/                   # teleop / collect / trajectory CLIs
```

## 4. 从零安装

### 4.1 系统前提

推荐环境：

- Ubuntu 22.04/24.04。
- Python `3.12`。`pyproject.toml` 当前要求 `>=3.12`。
- 算法机需要桌面环境才能使用 OpenCV 显示窗口、键盘遥操作和数据播放器。
- 控制机需要 Franka FCI 环境、PREEMPT_RT 内核、`aiofranka`、`pylibfranka`。

建议先安装基础系统包：

```bash
sudo apt update
sudo apt install -y git build-essential cmake pkg-config
sudo apt install -y libhidapi-hidraw0 libhidapi-libusb0
sudo apt install -y libgl1 libglib2.0-0
```

### 4.2 算法机安装

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control

conda create -n franka python=3.12 -y
conda activate franka

python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

如果不用 `pyproject.toml`，也可以：

```bash
python -m pip install -r requirements.txt
python -m pip install -e .
```

安装后验证：

```bash
python -c "import franka_control; print('franka_control import ok')"
python -m pytest tests -q
```

### 4.3 控制机安装

控制机也需要本仓库：

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control

conda create -n franka python=3.12 -y
conda activate franka

python -m pip install -U pip setuptools wheel
python -m pip install -e .
```

控制机额外需要 Franka 控制依赖：

```bash
python -m pip install -e ".[control-machine]"
```

如果 `pylibfranka` 或 `aiofranka` 无法直接通过 pip 安装，请按你控制机的 Franka FCI 安装方式单独安装。算法机不需要这两个包。

### 4.4 SpaceMouse 权限

如果使用 SpaceMouse，在算法机配置 udev：

```bash
sudo tee /etc/udev/rules.d/99-spacemouse.rules > /dev/null << 'RULES'
SUBSYSTEM=="usb", ATTRS{idVendor}=="256f", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="256f", MODE="0666"
RULES
sudo udevadm control --reload-rules
sudo udevadm trigger
```

然后拔插 SpaceMouse。

### 4.5 OpenCV 显示环境

本项目的数据采集预览和播放器需要 GUI 版 OpenCV，也就是 `opencv-python`。如果你的环境里同时装了 `opencv-python-headless`，可能出现窗口无法显示或 Qt/HighGUI 行为异常。

推荐算法机使用：

```bash
python -m pip uninstall -y opencv-python-headless
python -m pip install -U opencv-python
```

如果在无显示器/SSH headless 环境运行采集：

```bash
python -m franka_control.scripts.collect_episodes ... --display off
```

### 4.6 RealSense 相机

编辑 `config/cameras.yaml`：

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

`enable_depth` 和 `depth` 都兼容。采集脚本当前只保存 RGB 图像；depth 由 `CameraManager` 支持，但默认不写入 LeRobot features。

## 5. 网络和硬件启动流程

下面假设：

- Franka FCI IP：`192.168.0.2`
- 控制机 IP：`192.168.0.100`
- 算法机 IP：`192.168.0.200`

### 5.1 检查网络

在算法机：

```bash
ping 192.168.0.100
```

控制机防火墙需要允许：

```bash
sudo ufw allow 5555/tcp
sudo ufw allow 5556/tcp
sudo ufw allow 5557/tcp
```

### 5.2 启动 RobotServer

在控制机终端 1：

```bash
conda activate franka
python -m franka_control.robot \
    --fci-ip 192.168.0.2 \
    --port 5555 \
    --state-stream-port 5557 \
    --poll-hz 1000
```

### 5.3 启动 GripperServer

在控制机终端 2：

```bash
conda activate franka
python -m franka_control.gripper \
    --robot-ip 192.168.0.2 \
    --port 5556
```

这里 `--robot-ip` 是 Franka 机器人本体 IP，因为 GripperServer 直接连 Franka gripper。

### 5.4 算法机验证连接

在算法机：

```bash
conda activate franka
python -m franka_control.scripts.measure_latency \
    --robot-ip 192.168.0.100 \
    -n 100
```

如果能看到 `get_state` / `set` 延迟统计，说明算法机可以连接 RobotServer。

## 6. 最小真机使用流程

新手建议按这个顺序：

1. 控制机启动 `RobotServer` 和 `GripperServer`。
2. 算法机运行 `measure_latency` 验证网络。
3. 算法机运行 `teleop`，低速确认机器人能安全移动。
4. 用 `collect_waypoints` 采集几个 waypoint。
5. 用 `run_trajectory --dry-run` 检查轨迹。
6. 用 `run_trajectory --time-scale 3.0` 慢速执行。
7. 配好相机后运行 `collect_episodes` 采集数据。
8. 用 `scripts/play_dataset.py` 回放和检查数据。

## 7. 遥操作

### 7.1 SpaceMouse 遥操作

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device spacemouse \
    --action-scale-t 2.0 \
    --action-scale-r 5.0 \
    --hz 100
```

控制：

- SpaceMouse 6 自由度控制末端增量。
- 左键关闭夹爪。
- 右键打开夹爪。
- `Ctrl+C` 退出。

### 7.2 键盘遥操作

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device keyboard \
    --action-scale-t 1.0 \
    --action-scale-r 2.5 \
    --hz 100
```

控制：

| 按键 | 作用 |
|---|---|
| `W/S` | `+X / -X` |
| `A/D` | `+Y / -Y` |
| `R/F` | `+Z / -Z` |
| `Q/E` | `+Yaw / -Yaw` |
| `Z/X` | `+Pitch / -Pitch` |
| `C/V` | `+Roll / -Roll` |
| `Space` | 关闭夹爪 |
| `Enter` | 打开夹爪 |
| `Shift` | 慢速模式，0.25x |
| `Esc` | 退出 |

只做平移、不允许旋转：

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device spacemouse \
    --freeze-rotation
```

## 8. Waypoint 采集和轨迹执行

### 8.1 采集 waypoint

SpaceMouse：

```bash
python -m franka_control.scripts.collect_waypoints \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml \
    --device spacemouse
```

键盘：

```bash
python -m franka_control.scripts.collect_waypoints \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml \
    --device keyboard
```

SpaceMouse 模式命令键：

| 按键 | 作用 |
|---|---|
| `r` | 记录当前关节角为 waypoint |
| `g` | 移动到已有 waypoint |
| `p` | 创建 route |
| `d` | 删除 waypoint 或 route |
| `l` | 列出全部 waypoint 和 route |
| `w` | 保存 YAML |
| `q` | 退出并自动保存 |

键盘模式为了避免和移动键冲突，命令键是数字：

| 按键 | 作用 |
|---|---|
| `1` | 记录 waypoint |
| `2` | 移动到 waypoint |
| `3` | 创建 route |
| `4` | 删除 waypoint 或 route |
| `5` | 列出全部 |
| `6` | 保存 |
| `Esc` | 退出并自动保存 |

### 8.2 Waypoint YAML 格式

```yaml
waypoints:
  home:
    joint_angles: [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
    label: "safe home"
  above_obj:
    joint_angles: [0.1, -0.5, 0.2, -2.0, 0.1, 1.3, 0.5]
    label: "above object"

routes:
  pick_place:
    label: "pick and place"
    waypoints: [home, above_obj, grasp, above_obj, release]
    gripper_actions:
      grasp: close
      release: open
```

`gripper_actions` 的 key 是 route 中的 waypoint 名称。执行到对应段时会触发阻塞式 `close/open`。

### 8.3 Dry-run 规划

先不连机器人，只检查 route 是否能规划：

```bash
python -m franka_control.scripts.run_trajectory \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --dry-run
```

### 8.4 慢速真机执行

首次执行推荐减速：

```bash
python -m franka_control.scripts.run_trajectory \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --time-scale 3.0
```

循环执行：

```bash
python -m franka_control.scripts.run_trajectory \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --time-scale 3.0 \
    --loop
```

常用参数：

| 参数 | 默认 | 说明 |
|---|---:|---|
| `--control-hz` | `200` | 轨迹采样率 |
| `--vel-scale` | `1.0` | 速度限制缩放 |
| `--acc-scale` | `1.0` | 加速度限制缩放 |
| `--time-scale` | `1.0` | 执行时间拉伸，`3.0` 表示约 1/3 速度 |

## 9. 数据采集

### 9.1 数据格式

采集保存为 LeRobot v3 数据集。默认字段：

| 字段 | shape | 说明 |
|---|---:|---|
| `observation.state` | `(8,)` | `q0..q6 + gripper_width` |
| `observation.joint_vel` | `(7,)` | 关节速度 |
| `observation.ee_pose` | `(7,)` | `x,y,z,qx,qy,qz,qw`，四元数顺序是 SciPy `xyzw` |
| `observation.effort` | `(7,)` | 关节力矩 |
| `action` | `(8,)` 或 `(7,)` | 取决于 `control_mode` |
| `observation.images.<camera>` | `(H,W,3)` | RGB 图像，通常视频编码 |
| `task` | string | LeRobot task 文本 |

动作维度：

| `control_mode` | action 格式 |
|---|---|
| `joint_abs` | `[q0,q1,q2,q3,q4,q5,q6,gripper]` |
| `joint_delta` | `[dq0,dq1,dq2,dq3,dq4,dq5,dq6,gripper]` |
| `ee_abs` | `[x,y,z,rx,ry,rz,gripper]` |
| `ee_delta` | `[dx,dy,dz,drx,dry,drz,gripper]` |

成功/失败标注保存在：

```text
<dataset_root>/meta/episode_annotations.json
```

### 9.2 配置相机

确认 `config/cameras.yaml` 中 serial 是真实相机 serial。无相机时可以加 `--no-camera`。

### 9.3 采集 episode

SpaceMouse，推荐用于采集：

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
    --cameras config/cameras.yaml \
    --display auto
```

键盘采集：

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

无相机采集：

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_state_only \
    --root data/franka_state_only \
    --task-name "state only test" \
    --no-camera \
    --display off
```

继续已有数据集：

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_pick \
    --root data/franka_pick \
    --resume \
    --num-episodes 20
```

保存失败 episode：

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id user/franka_pick \
    --root data/franka_pick \
    --save-failure
```

### 9.4 采集交互按键

SpaceMouse 模式：

| 输入 | 作用 |
|---|---|
| SpaceMouse | 6DoF 运动 |
| 左键 | 关闭夹爪 |
| 右键 | 打开夹爪 |
| `s` | 开始录制 |
| `e` | 结束 episode 并询问 success/failure |
| `f` | 丢弃当前 episode / 跳过 |
| `q` | 退出 |

Keyboard 模式：

| 输入 | 作用 |
|---|---|
| `W/S A/D R/F` | 平移 |
| `Q/E Z/X C/V` | 旋转 |
| `Space` | 关闭夹爪 |
| `Enter` | 打开夹爪 |
| `Shift` | 慢速 |
| `s` | preview 阶段开始录制 |
| `Esc` | 结束当前 episode |

说明：

- 数据层使用 `StateStreamRecorder` 后台读取机器人状态和相机帧，夹爪阻塞动作期间也能持续记录状态/图像。
- 显示窗口依赖 OpenCV GUI。无 GUI 环境请使用 `--display off`。
- `collect_episodes.py` 当前是推荐采集入口，`collect_data.py` 是旧版兼容脚本。

## 10. 数据集播放器

播放并检查采集结果：

```bash
python scripts/play_dataset.py \
    --repo-id user/franka_pick \
    --root data/franka_pick
```

播放器按键：

| 按键 | 功能 |
|---|---|
| `Space` | 播放/暂停 |
| `←/→` | 上/下一帧 |
| `[` / `]` | 上/下 episode |
| `g` | 输入真实 episode index 跳转 |
| `,` / `.` | 减速/加速，档位 `0.25x,0.5x,1x,2x,4x` |
| `Home/End` | 跳到当前 episode 首/尾 |
| `1-9` | 切换单相机 |
| `0` | 显示全部相机 |
| `h` | 切换普通/详细 HUD |
| `f` | 循环过滤 `all/success/failure` |
| `t` | 按 task 过滤 |
| `l` | 在终端打印 episode 列表 |
| `p` | 保存当前帧所有相机截图到 `screenshots/` |
| `v` | 显示 joint/EE/gripper 轨迹 |
| `a` | 显示 action 分布和时间序列 |
| `i` | 在终端打印 action 统计表 |
| `s` | 导出当前 episode MP4 到 `videos/` |
| `q` / `Esc` | 退出 |

## 11. Python API

### 11.1 FrankaEnv

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

# ee_delta: dx,dy,dz,drx,dry,drz,gripper
action = np.array([0.01, 0.0, 0.0, 0.0, 0.0, 0.0, 1.0], dtype=np.float32)
obs, reward, terminated, truncated, info = env.step(action)
print(info["applied_action"])

env.close()
```

### 11.2 DataCollector

`DataCollector` 是纯记录器，不控制机器人、不读相机。调用方负责传入 obs/action/images。

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
action = np.zeros(7, dtype=np.float32)

collector.record_frame(obs, action, images=None)
collector.end_episode(success=True)
collector.finalize()
```

自定义额外 feature：

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

collector.record_frame(
    obs,
    action,
    extra={"observation.phase": np.array([1, 0, 0], dtype=np.int32)},
)
```

### 11.3 CameraManager

```python
from franka_control.cameras import CameraManager

cameras = CameraManager.from_yaml("config/cameras.yaml")
frames = cameras.read()
latest = cameras.read_latest()

rgb = frames["d435"]["rgb"]
cameras.close()
```

### 11.4 FK/IK

```python
import numpy as np
from franka_control.kinematics import IKSolver

solver = IKSolver()
q = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])

T = solver.fk(q)
q_solution, converged = solver.ik(q, T)
```

验证脚本：

```bash
python -m franka_control.kinematics.verify_fk --robot-ip 192.168.0.100
python -m franka_control.kinematics.verify_ik --robot-ip 192.168.0.100
```

## 12. 开发和测试

运行全部测试：

```bash
python -m pytest tests -q
```

只测数据采集：

```bash
python -m pytest tests/test_data_collection.py -q
```

语法检查：

```bash
python -m py_compile \
    franka_control/data/collector.py \
    franka_control/data/features.py \
    franka_control/data/state_recorder.py \
    franka_control/scripts/collect_episodes.py \
    scripts/play_dataset.py
```

## 13. 常见问题

| 问题 | 常见原因 | 处理 |
|---|---|---|
| `Server timeout` | 算法机连不上控制机 | 检查 `--robot-ip`、ping、防火墙、端口 5555/5556/5557 |
| `Failed to connect to robot` | RobotServer 未启动或 FCI 未解锁 | 控制机启动服务，Desk 解锁 FCI |
| `aiofranka is not installed` | 控制机缺控制依赖 | 控制机安装 `aiofranka` |
| `pylibfranka` import 失败 | 控制机缺 Franka gripper 依赖 | 控制机安装 `pylibfranka` |
| `Worker busy` | 上一个阻塞命令还在执行 | 等待完成；必要时重启 RobotServer |
| `Already connected` | RobotServer 仍持有旧连接 | 重启 RobotServer |
| Gripper homing 超时 | 首次 homing 慢或夹爪连接异常 | 等待后重试，必要时重启 GripperServer |
| SpaceMouse 无输入 | HID 权限或设备未识别 | 配 udev 规则，拔插设备 |
| 键盘无输入 | 没有桌面环境或窗口焦点问题 | 在本地桌面运行，确认终端/窗口焦点 |
| OpenCV 窗口不显示 | headless 环境或装了 headless OpenCV | 用 `--display off` 或安装 `opencv-python` |
| RealSense timeout | serial 错误、USB 带宽不足、相机被占用 | 检查 `config/cameras.yaml`、换 USB 口、关闭占用程序 |
| 数据集 resume feature mismatch | 配置 camera/control_mode/extra_features 和旧数据集不一致 | 保持同一配置 resume，或新建数据集 |
| `Cannot finalize with active episode` | 还有未结束 episode | 先 `end_episode()` 或 `discard_episode()` |
| 播放器打不开 | 没有 GUI OpenCV 或 matplotlib | 安装 `opencv-python matplotlib`，在桌面环境运行 |

## 14. 术语速查

| 术语 | 含义 |
|---|---|
| FCI IP | Franka 机器人本体控制接口 IP |
| 控制机 IP | 运行 RobotServer/GripperServer 的电脑 IP |
| 算法机 | 运行遥操作、采集、训练/推理脚本的电脑 |
| `joint_abs` | 绝对关节角控制 |
| `joint_delta` | 关节角增量控制 |
| `ee_abs` | 末端绝对位姿控制，旋转为 rotvec |
| `ee_delta` | 末端增量控制，旋转为 rotvec |
| LeRobot dataset | `data/`, `videos/`, `meta/` 组成的数据集目录 |
| task | LeRobot 任务文本，例如 `"pick red cube"` |
| success annotation | 本仓库额外保存的 episode 成功/失败 JSON |
