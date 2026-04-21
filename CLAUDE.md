# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

Franka Research 3 机械臂控制库。双机架构：算法机（GPU, Python）通过 TCP ZMQ 控制机（RT kernel）。
提供 Gymnasium 环境、遥操作、TOPPRA 轨迹规划、LeRobot 格式数据采集。

用户负责架构和规划设计，Claude Code 负责执行实现。目标开源。

## 协作方式（黄金法则）

1. **用户是大脑，Claude Code 是双手** — 永远不要全权委托，用户确认方案后再编码
2. **先规划，后编码** — 任何任务先只出方案不写代码
3. **一次只做一件小事** — 拆小步骤，每步用户验证后再进下一步
4. **维护 CLAUDE.md** — 项目概述、架构、进度、已知问题写在这里
5. **Debug 先问为什么** — 先解释根因和多种可能，用户判断后再修
6. **拒绝膨胀** — 每阶段完成后审查清理死代码和临时补丁
7. **教用户** — 用户问就解释，帮用户理解

## 开发命令

### 安装依赖

```bash
# 算法机（基础依赖）
pip install numpy scipy gymnasium pyyaml pyzmq msgpack

# 按需安装
pip install toppra          # 轨迹规划
pip install pin             # 运动学（FK/IK），注意：不是 pinocchio 包
pip install pyspacemouse    # 遥操作
pip install pyrealsense2    # 相机
pip install lerobot         # 数据采集

# 控制机专用（需要 Franka FCI）
pip install pylibfranka aiofranka
```

有 `pyproject.toml`（setuptools backend），可用 `pip install -e .` 安装。

### 运行测试

```bash
python -m pytest tests/ -v            # 全部测试
python -m pytest tests/test_gripper.py -v  # 单个测试文件
python -m pytest tests/ -k "test_name" -v  # 单个测试用例
```

测试可直接在仓库根目录运行；当前 pytest root/config 由 `pyproject.toml` 提供。

测试覆盖：`test_gripper.py`（23 个测试用例）、`test_keyboard_teleop.py`（8 个测试用例），共 31 个测试。其余模块（env、robot、spacemouse_teleop、camera、data、trajectory）暂无测试。

### 启动服务（控制机）

```bash
python -m franka_control.robot --fci-ip <FRANKA_FCI_IP>     # RobotServer, 端口 5555
python -m franka_control.gripper --robot-ip <FRANKA_FCI_IP>  # GripperServer, 端口 5556
```

### 运行脚本（算法机）

```bash
python -m franka_control.scripts.teleop --robot-ip <控制机IP>
python -m franka_control.scripts.teleop --robot-ip <控制机IP> --device keyboard  # 键盘遥操作
python -m franka_control.scripts.collect_data --robot-ip <控制机IP>
python -m franka_control.scripts.collect_waypoints --robot-ip <控制机IP> --waypoints config/waypoints.yaml
python -m franka_control.scripts.run_trajectory --robot-ip <控制机IP> --waypoints config/waypoints.yaml --route <route_name>
python -m franka_control.scripts.run_trajectory --waypoints config/waypoints.yaml --route <route_name> --dry-run  # 无需真机
python -m franka_control.scripts.measure_latency --robot-ip <控制机IP>  # ZMQ 延迟测量
```

**IP 参数说明：**
- `--fci-ip`：Franka 机器人的 FCI IP（如 192.168.0.2），仅控制机启动 RobotServer 时使用
- `--robot-ip`：控制机的 IP（算法机连接目标），算法机所有脚本使用
- `--gripper-host`：Gripper 服务器地址，默认等于 robot-ip

## 项目结构

```
franka_control/
├── robot/                   # 双机 TCP 桥接（robot_server + robot_client）
├── gripper/                 # 夹爪 ZMQ 服务（gripper_server + gripper_client）
├── envs/franka_env.py       # Gymnasium 环境
├── kinematics/              # FK/IK 求解器（Pinocchio）
│   ├── ik_solver.py         # IKSolver 类
│   ├── assets/              # FR3v2 URDF + mesh 文件
│   ├── verify_fk.py         # FK 验证脚本
│   └── verify_ik.py         # IK 验证脚本
├── teleop/                  # SpaceMouse + Keyboard 遥操作
├── cameras/camera_manager.py # RealSense 多相机管理
├── data/collector.py        # LeRobot 格式数据采集
├── trajectory/              # Waypoint YAML + TOPPRA 轨迹规划
└── scripts/                 # teleop / collect_data / collect_waypoints / run_trajectory / measure_latency
```

## 架构

```
算法机 (Python)                          控制机 (RT kernel)
├── FrankaEnv (Gymnasium)                ├── RobotServer (TCP 5555)
│   └── RobotClient (ZMQ DEALER)         │   └─ FrankaRemoteController
│       └─ PULL 状态接收 (port 5557)     │       └─ aiofranka 子进程 (IPC/SharedMemory)
├── IKSolver (Pinocchio)                 ├── GripperServer (TCP 5556)
├── 遥操作 (SpaceMouse/Keyboard)          │   └─ pylibfranka.Gripper
├── TOPPRA 轨迹规划                       └── Franka Research 3
├── 数据采集 (LeRobot 格式)
└── 相机管理 (RealSense)
```

### 通信层

- ZMQ ROUTER/DEALER + msgpack 序列化（阻塞命令：connect/start/move/switch/get_state）
- ZMQ PUSH/PULL 状态流（端口 5557）：服务端 1kHz 推送，客户端后台接收最新帧
- set() 命令 fire-and-forget：客户端只发不等回复，服务端 latest-wins 单槽处理
- numpy 数组序列化为 bytes + shape 元数据
- GripperServer 使用 3 线程模式：主循环（ZMQ recv）、worker 线程（阻塞 pylibfranka 调用）、状态轮询线程
- RobotServer 使用 2 线程模式：主循环（ZMQ recv）+ 控制器线程（拥有 FrankaRemoteController，连接/轮询在同一线程）；阻塞操作（move）生成临时辅助线程
- RobotServer 通过线程亲和性保护 aiofranka 访问（仅控制器线程接触 `self._controller`）

### 模块依赖关系

- `FrankaEnv` → `RobotClient` + `GripperClient`（不直接依赖 aiofranka）
- `IKSolver`（纯 Pinocchio FK/IK，零项目内依赖）→ 内置 FR3v2 URDF + mesh
- `TrajectoryPlanner`（纯 TOPPRA 规划，零项目内依赖）→ `WaypointStore`（YAML 数据层）
- `executor.py`（route 拆分 + 执行）→ `planner` + `waypoints` + `FrankaEnv`
- Scripts → `FrankaEnv` / `TrajectoryPlanner` / `WaypointStore` / `SpaceMouseTeleop` / `KeyboardTeleop`
- 可选依赖通过 try/except 优雅降级（aiofranka, pylibfranka, pyspacemouse, pynput, pyrealsense2, pin）；lerobot 无保护，导入即依赖
- `trajectory/__init__.py` 为空，不做 re-export（避免 toppra 成为包级硬依赖）
- `kinematics/assets/` 包含 FR3v2 URDF + mesh 文件（从 frankarobotics/franka_description 生成）

### FrankaEnv 核心

- 4 种 action_mode：`joint_abs` / `joint_delta` / `ee_abs` / `ee_delta`
- 2 种 gripper_mode：`continuous` / `binary`
- `reset()` 自动错误恢复 + 回 home
- `step(action)` 最后一维是 gripper
- `move_to(qpos)` 阻塞式 Ruckig 移动
- `set_action_mode(mode)` 运行时热切换
- `_clip_safety()` 做关节限位（Safety Box Wrapper 未独立实现）
- RL/遥操作/轨迹执行/回放统一走 `env.step(action)`

### 关键常量

- Home 位置：`[0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]` rad
- 关节 delta 限制：±0.1 rad/step
- 夹爪最大宽度：0.08m，默认抓力 40N
- 遥操作默认参数：100Hz、平移 2.0 m/s、旋转 5.0 rad/s（速度模式，频率无关）
- 遥操作设备：SpaceMouse（后台进程轮询）和 Keyboard（pynput 真实 keydown/keyup），通过 `--device` 选择
- `freeze_rotation`：构造参数 + `set_freeze_rotation()` 运行时切换，冻结旋转只保留平移
- 轨迹规划约束：aiofranka 参数的 80%（vel ~8 rad/s, acc ~4 rad/s²）
- 轨迹执行：PID 无速度前馈（aiofranka 限制，仅 q_desired/ee_desired/torque），用 `--time-scale` 减速
- ZMQ 超时：RobotClient 5s socket / 60s connect/start / 30s move；GripperClient 10s socket

## Python API 示例

### FrankaEnv 基本使用

```python
from franka_control.envs import FrankaEnv
import numpy as np

env = FrankaEnv(
    robot_ip="192.168.0.100",    # 控制机 IP
    action_mode="joint_abs",      # joint_abs / joint_delta / ee_abs / ee_delta
    gripper_mode="binary",        # binary / continuous
)

obs, _ = env.reset()
action = np.append(obs["joint_pos"], 1.0)  # +1 维 gripper (1.0=open, 0.0=close)
obs, reward, terminated, truncated, info = env.step(action)

env.set_action_mode("ee_delta")  # 运行时切换模式
env.move_to(target_qpos)         # 阻塞式移动
env.close()
```

### 轨迹规划与执行

```python
from franka_control.trajectory.planner import TrajectoryPlanner
from franka_control.trajectory.executor import execute_route
from franka_control.trajectory.waypoints import WaypointStore

store = WaypointStore()
store.load("config/waypoints.yaml")
planner = TrajectoryPlanner()

# 在真机上执行 route（time_scale 减速）
execute_route(env, store, "pick_place", planner, time_scale=3.0)
```

### 运动学（FK/IK）

```python
from franka_control.kinematics import IKSolver
import numpy as np

# 默认加载 FR3v2 + 法兰坐标系
solver = IKSolver()

# 正运动学：关节角 → 末端位姿
q = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])
T = solver.fk(q)  # 4x4 齐次变换矩阵
print(f"Position: {T[:3, 3]}")

# 逆运动学：末端位姿 → 关节角
q_init = q  # 初值
q_solution, converged = solver.ik(q_init, T)
if converged:
    print(f"IK solution: {q_solution}")
```

**验证脚本：**
```bash
# FK 验证（对比真机状态）
python -m franka_control.kinematics.verify_fk --robot-ip <控制机IP>

# IK 验证（多构型收敛性测试）
python -m franka_control.kinematics.verify_ik --robot-ip <控制机IP>
```

### Waypoint YAML 格式

```yaml
waypoints:
  home:
    joint_angles: [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]
    label: "安全起始位"

routes:
  pick_place:
    waypoints: [home, above_table, grasp_pos, home]
    gripper_actions:
      grasp_pos: close
```

## 常见问题排查

| 问题 | 原因 | 解决 |
|------|------|------|
| `Server timeout` | 算法机连不上控制机 | 检查 IP、防火墙、端口 5555/5556 |
| `Robot command failed: stop` | 机器人未解锁或 FCI 未启动 | Desk 网页解锁 FCI |
| `Reflex` 模式导致 connect 失败 | disconnect 后机器人进入错误保护 | RobotServer 会自动调用 `automatic_error_recovery()` |
| `aiofranka is not installed` | 控制机未安装 aiofranka | 控制机上 `pip install aiofranka` |
| `Worker busy` | 上一个阻塞命令还在执行 | 等待完成，或重启 RobotServer |
| `Already connected` | RobotServer 已有连接 | 重启 RobotServer |
| Gripper homing 超时 | 首次 homing 较慢 | 客户端 RCVTIMEO 已设为 10s，重启 GripperServer 后重试 |
| `No module named 'pinocchio'` | 未安装 pin 包 | `pip install pin`（不是 pinocchio） |
| `pinocchio has no attribute buildModelFromUrdf` | 安装了错误的 pinocchio 包 | `pip uninstall pinocchio && pip install pin` |

## 关键设计决策

- aiofranka 不修改，固定在控制机，通过 RobotServer TCP 桥接暴露
- 上层借鉴 serl_robot_infra 设计模式（Gym Env、遥操作），重新实现
- 轨迹规划在算法机离线完成（样条+TOPPRA），采样后逐点 `env.step()` 执行；PID 无速度前馈，用 `--time-scale 3.0` 减速（经验值）
- 夹爪独立进程+ZMQ（aiofranka 的 GripperController 是 Robotiq，本项目新建 Franka Gripper 版本）
- **夹爪动作必然阻塞机械臂**：pylibfranka.Gripper.grasp()/move() 在 C++ 层（libfranka）就是同步阻塞的，Franka FCI 同一时间只允许一个活跃控制连接。即使 GripperServer 用 worker 线程隔离，机械臂控制仍被挂起直到夹爪完成（grasp ~1-2s，move ~0.5s）。架构层面无法规避，这是 Franka 硬件限制。
- 算法机和控制机共用一个代码仓库
- **运动学模块写死 FR3 家族**：当前固定 fr3v2 + 法兰坐标系（fr3v2_link8），URDF/mesh 内置于 `kinematics/assets/`。真机报告的 `state["ee"]` 是法兰坐标系（不是 fr3v2_hand，两者差 45° Z 轴旋转）。IK 使用 Jacobian 伪逆迭代 + 关节限位 clamp，7-DOF 冗余导致解不唯一。URDF 来源：[frankarobotics/franka_description](https://github.com/frankarobotics/franka_description)

## 参考库

- [aiofranka (Improbable-AI)](https://github.com/Improbable-AI/aiofranka) — 底层控制
- [serl_robot_infra (HIL-SERL)](https://github.com/rail-berkeley/hil-serl) — 上层 Env/遥操作设计参考
- [LeRobot (HuggingFace)](https://github.com/huggingface/lerobot) — 数据格式
- [Franka Robotics 官方文档](https://frankarobotics.github.io/docs/overview.html)

## 当前进度

所有 5 个 Phase 已完成：Gripper → Env → 遥操作/相机/数据采集 → 轨迹规划 → 双机 TCP 桥接。
Trajectory 模块已重构（planner/executor/waypoints 三层分离）并通过真机验收（pick_place route）。
**Kinematics 模块已完成**：IKSolver（Pinocchio）提供 FK/IK，内置 FR3v2 URDF，真机验证通过（FK 0mm 误差，IK 全构型收敛）。
已知 BUG 已修复（夹爪 binary 模式重复 grasp、keyboard exit_requested 不重置、input() Enter 残留）。
Scripts 已从独立目录移入 `franka_control/scripts/`。

### 未解决问题

**中等问题（8-18，非关键优化，暂未处理）：**
- 8-10: gripper_server 参数校验、stop 结果重置、轮询退避
- 11-13: spacemouse 非原子读取、按钮假设、参数验证
- 14-15: camera_manager 关闭竞态、静默旧帧
- 16-17: collector gripper 填零、lerobot API 兼容
- 18: 常量重复定义

**待讨论（TBD）：**
- 安全限位策略（当前 `_clip_safety()` 只做关节限位）
- 笛卡尔空间工作限制（Safety Box Wrapper 未实现）
- 碰撞检测
- episode 终止条件（当前始终返回 False）

**文档：** `docs/` 下为历史规划文档，与实际实现有偏差，仅供参考
