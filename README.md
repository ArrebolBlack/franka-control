# Franka Control

Franka Research 3 机械臂控制库。双机架构：算法机（GPU）通过 TCP 控制机（RT kernel）。
提供 Gym 环境、遥操作、轨迹规划、数据采集功能。

## 架构

```
算法机 (Python)                          控制机 (RT kernel)
├── FrankaEnv (Gymnasium)                ├── RobotServer (TCP 5555)
│   └── RobotClient (ZMQ DEALER)         │   └─ FrankaRemoteController (本地)
│       └─ PULL 状态接收 (port 5557)     │       └─ aiofranka 子进程 (IPC/SharedMemory)
├── 遥操作 (SpaceMouse/Keyboard)          ├── GripperServer (TCP 5556)
├── TOPPRA 轨迹规划                       │   └─ pylibfranka.Gripper (本地)
├── 数据采集 (LeRobot 格式)               └── Franka Research 3
└── 相机管理 (RealSense)
        ↕ TCP ZMQ (msgpack)
```

### 双机部署

- **控制机**：运行 RobotServer（端口 5555 + 状态流 5557）+ GripperServer（端口 5556），需要 aiofranka + pylibfranka
- **算法机**：运行 FrankaEnv / 脚本，通过 TCP ZMQ 与控制机通信，不需要安装 FCI 相关库
- **流式架构**：set() fire-and-forget + PUSH/PULL 状态流（1kHz），热路径零 RTT；阻塞命令（connect/move/start）仍走同步 RPC

### IP 参数说明

| 参数 | 含义 | 在哪里使用 |
|------|------|-----------|
| `--fci-ip` | Franka 机器人的 FCI IP（如 192.168.0.2） | 仅控制机启动 RobotServer 时 |
| `--robot-ip` | 控制机的 IP（算法机连接目标） | 算法机所有脚本 |
| `--gripper-host` | Gripper 服务器地址，默认 = robot-ip | 算法机（可选） |

## 项目结构

```
franka_control/
├── robot/                   # 双机 TCP 桥接层
│   ├── robot_server.py      # 控制机运行，包装 aiofranka
│   ├── robot_client.py      # 算法机运行，TCP 客户端
│   └── __main__.py          # python -m franka_control.robot
├── gripper/                 # 夹爪 ZMQ 服务端/客户端
│   ├── gripper_server.py    # 控制机运行，封装 pylibfranka.Gripper
│   ├── gripper_client.py    # 算法机运行，阻塞/非阻塞 API
│   └── __main__.py          # python -m franka_control.gripper
├── envs/
│   └── franka_env.py        # Gymnasium 环境
├── teleop/
│   ├── spacemouse_teleop.py # SpaceMouse 遥操作
│   └── keyboard_teleop.py  # 键盘遥操作
├── cameras/
│   └── camera_manager.py    # RealSense 多相机管理
├── data/
│   └── collector.py         # LeRobot 格式数据采集
├── trajectory/
│   ├── waypoints.py         # Waypoint/Route YAML 管理
│   └── planner.py           # TOPPRA 轨迹规划 + 执行
└── scripts/
    ├── teleop.py            # 遥操作
    ├── collect_data.py      # 数据采集
    ├── collect_waypoints.py # Waypoint 采集
    └── run_trajectory.py    # 轨迹执行
```

## 安装

```bash
# 算法机（基础依赖）
pip install numpy scipy gymnasium pyyaml pyzmq msgpack

# 轨迹规划
pip install toppra

# 遥操作 (需要 SpaceMouse)
sudo apt install libhidapi-hidraw0 libhidapi-libusb0
pip install pyspacemouse hidapi

# 遥操作 (键盘模式)
pip install pynput

# SpaceMouse USB 权限（免 sudo 访问 HID 设备）
sudo tee /etc/udev/rules.d/99-spacemouse.rules > /dev/null << 'RULES'
SUBSYSTEM=="usb", ATTRS{idVendor}=="256f", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="256f", MODE="0666"
RULES
sudo udevadm control --reload-rules && sudo udevadm trigger

# 相机
pip install pyrealsense2

# 数据采集
pip install lerobot

# 控制机专用（需要 Franka FCI）
pip install pylibfranka aiofranka
```

## 真机测试步骤

### 前提

1. Franka Research 3 已上电，FCI 已解锁（Desk 网页界面）
2. 控制机已安装 PREEMPT_RT 内核 + aiofranka + pylibfranka
3. 两台机器网络互通（算法机能 ping 通控制机）

### 网络配置示例

假设：
- Franka FCI IP：`192.168.0.2`（Franka 机器人自身 IP，在 Desk 里配置）
- 控制机 IP：`192.168.0.100`（与 FCI 在同一网段）
- 算法机 IP：`192.168.0.200`（与控制机在同一网段）

### 第1步：控制机启动服务

控制机上开两个终端：

```bash
# 终端1：启动 RobotServer（FCI IP 是机器人的 IP）
python -m franka_control.robot --fci-ip 192.168.0.2

# 终端2：启动 GripperServer（robot-ip 是 FCI IP）
python -m franka_control.gripper --robot-ip 192.168.0.2
```

两个终端应该分别显示：
```
Robot server listening on port 5555
Gripper server listening on port 5556
```

### 第2步：算法机验证连接

```bash
# 快速测试：算法机上用 Python 验证 TCP 连通
python -c "
from franka_control.robot.robot_client import RobotClient
c = RobotClient(host='192.168.0.100', port=5555)
print('Robot server reachable:', c._send_command('is_running'))
c.close()
"
```

如果成功应输出类似 `Robot server reachable: {'success': True, 'running': False}`。

### 第3步：算法机控制机器人

```bash
# 遥操作 — SpaceMouse（默认）
# 默认 100Hz, 平移 2.0 m/s, 旋转 5.0 rad/s（速度模式）
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100

# 遥操作 — 键盘
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 --device keyboard

# 调灵敏度（直接改最大速度）
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --action-scale-t 1.0 --action-scale-r 2.5

# 冻结旋转（只保留平移）
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 --freeze-rotation

# 或采集 waypoint
python -m franka_control.scripts.collect_waypoints \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml
```

**注意**：`--robot-ip` 是控制机 IP，不是 FCI IP。

### 第4步：执行轨迹

```bash
# 先 dry-run 验证轨迹规划
python -m franka_control.scripts.run_trajectory \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --dry-run

# 真机执行
python -m franka_control.scripts.run_trajectory \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml \
    --route pick_place
```

### 常见问题

| 问题 | 原因 | 解决 |
|------|------|------|
| `Server timeout` | 算法机连不上控制机 | 检查 IP、防火墙、端口 5555/5556 |
| `Robot command failed: stop` | 机器人未解锁或 FCI 未启动 | Desk 网页解锁 FCI |
| `Reflex` 模式导致 connect 失败 | disconnect 后机器人进入错误保护 | RobotServer 会自动调用 `automatic_error_recovery()`，通常无需干预 |
| `aiofranka is not installed` | 控制机未安装 aiofranka | 控制机上 `pip install aiofranka` |
| `Worker busy` | 上一个阻塞命令还在执行 | 等待完成，或重启 RobotServer |
| `Already connected` | RobotServer 已有连接 | 重启 RobotServer |
| Gripper homing 超时 | 首次 homing 较慢，pylibfranka C++ 调用持有 GIL | 客户端 RCVTIMEO 已设为 10s，重启 GripperServer 后重试 |

## Python API

### FrankaEnv

```python
from franka_control.envs import FrankaEnv
import numpy as np

env = FrankaEnv(
    robot_ip="192.168.0.100",    # 控制机 IP（RobotServer 地址）
    gripper_host="192.168.0.100", # Gripper 服务器（默认同 robot_ip）
    action_mode="joint_abs",      # joint_abs / joint_delta / ee_abs / ee_delta
    gripper_mode="binary",        # binary / continuous
)

obs, _ = env.reset()

# 关节绝对位置控制 (joint_abs)
action = obs["joint_pos"]  # (7,) rad
obs, reward, terminated, truncated, info = env.step(
    np.append(action, 1.0)  # +1 维 gripper (1.0=open, 0.0=close)
)

# 末端增量控制 (ee_delta)
env.set_action_mode("ee_delta")
action = np.array([0.01, 0, 0, 0, 0, 0, 1.0])  # xyz + rotvec + gripper
obs, _, _, _, _ = env.step(action)

# 阻塞式移动到目标关节角
env.move_to(target_qpos)

env.close()
```

### 轨迹规划

```python
from franka_control.trajectory.planner import TrajectoryPlanner, execute_route
from franka_control.trajectory.waypoints import WaypointStore
import numpy as np

store = WaypointStore()
store.load("config/waypoints.yaml")

planner = TrajectoryPlanner(
    vel_scale=1.0,  # 默认 aiofranka 参数的 80%
    acc_scale=1.0,
)

# 在真机上执行完整 route
execute_route(env, store, "pick_place", planner)
```

## Waypoint YAML 格式

```yaml
waypoints:
  home:
    joint_angles: [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
    label: "安全起始位"
  above_table:
    joint_angles: [0.1, -0.5, 0.2, -2.0, 0.1, 1.3, 0.5]
    label: "桌面正上方"

routes:
  pick_place:
    waypoints: [home, above_table, grasp_pos, lift_pos, home]
    gripper_actions:
      grasp_pos: close
      lift_pos: open
    label: "抓取放置"
```

## 测试

```bash
python -m pytest tests/ -v
```

## 硬件要求

- **机器人**：Franka Research 3 + FCI 许可
- **控制机**：Ubuntu 24 + PREEMPT_RT 内核，运行 RobotServer + GripperServer
- **算法机**：Python 3.10+，通过 TCP ZMQ 与控制机通信
- **遥操作**：3Dconnexion SpaceMouse Compact 或键盘（需桌面环境）
- **相机**（可选）：Intel RealSense（D435 等）
