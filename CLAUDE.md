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
pip install pyspacemouse    # 遥操作
pip install pyrealsense2    # 相机
pip install lerobot         # 数据采集

# 控制机专用（需要 Franka FCI）
pip install pylibfranka aiofranka
```

没有 pyproject.toml / setup.py，当前手动 pip 安装。

### 运行测试

```bash
python -m pytest tests/ -v            # 全部测试
python -m pytest tests/test_gripper.py -v  # 单个测试文件
python -m pytest tests/ -k "test_name" -v  # 单个测试用例
```

### 启动服务（控制机）

```bash
python -m franka_control.robot --fci-ip <FRANKA_FCI_IP>     # RobotServer, 端口 5555
python -m franka_control.gripper --robot-ip <FRANKA_FCI_IP>  # GripperServer, 端口 5556
```

### 运行脚本（算法机）

```bash
python -m franka_control.scripts.teleop --robot-ip <控制机IP>
python -m franka_control.scripts.collect_data --robot-ip <控制机IP>
python -m franka_control.scripts.collect_waypoints --robot-ip <控制机IP> --waypoints config/waypoints.yaml
python -m franka_control.scripts.run_trajectory --robot-ip <控制机IP> --waypoints config/waypoints.yaml --route <route_name>
python -m franka_control.scripts.run_trajectory --waypoints config/waypoints.yaml --route <route_name> --dry-run  # 无需真机
```

### IP 参数说明

| 参数 | 含义 | 使用场景 |
|------|------|----------|
| `--fci-ip` | Franka 机器人 FCI IP | 仅控制机启动 RobotServer 时 |
| `--robot-ip` | 控制机 IP（算法机连接目标） | 算法机所有脚本 |
| `--gripper-host` | Gripper 服务器地址，默认 = robot-ip | 算法机（可选） |

## 架构

```
算法机 (Python)                          控制机 (RT kernel)
├── FrankaEnv (Gymnasium)                ├── RobotServer (TCP 5555)
│   └── RobotClient (ZMQ DEALER)         │   └─ FrankaRemoteController
│                                        │       └─ aiofranka 子进程 (IPC/SharedMemory)
├── SpaceMouse 遥操作                     ├── GripperServer (TCP 5556)
├── TOPPRA 轨迹规划                       │   └─ pylibfranka.Gripper
├── 数据采集 (LeRobot 格式)               └── Franka Research 3
└── 相机管理 (RealSense)
        ↕ TCP ZMQ (msgpack 序列化)
```

### 通信层

- ZMQ ROUTER/DEALER + msgpack 序列化
- numpy 数组序列化为 bytes + shape 元数据
- RobotServer / GripperServer 均使用 3 线程模式：主循环（ZMQ recv）、worker 线程（阻塞操作）、状态轮询线程
- `_controller_lock` 保护 aiofranka 访问，`_controller_ready` 门控连接完成前的状态轮询

### 模块依赖关系

- `FrankaEnv` → `RobotClient` + `GripperClient`（不直接依赖 aiofranka）
- `TrajectoryPlanner` → `WaypointStore` + 从 `FrankaEnv` 导入关节限位常量
- Scripts → `FrankaEnv` / `TrajectoryPlanner` / `WaypointStore` / `SpaceMouseTeleop`
- 可选依赖通过 try/except 优雅降级（aiofranka, pylibfranka, pyspacemouse, pyrealsense2）

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
- 轨迹规划约束：aiofranka 参数的 80%（vel ~8 rad/s, acc ~4 rad/s²）
- ZMQ 超时：5s socket, 60s connect/start, 30s move

## 关键设计决策

- aiofranka 不修改，固定在控制机，通过 RobotServer TCP 桥接暴露
- 上层借鉴 serl_robot_infra 设计模式（Gym Env、遥操作），重新实现
- 轨迹规划在算法机离线完成（样条+TOPPRA），采样后逐点 `env.step()` 执行
- 夹爪独立进程+ZMQ（aiofranka 的 GripperController 是 Robotiq，本项目新建 Franka Gripper 版本）
- 算法机和控制机共用一个代码仓库

## 参考库

- [aiofranka (Improbable-AI)](https://github.com/Improbable-AI/aiofranka) — 底层控制
- [serl_robot_infra (HIL-SERL)](https://github.com/rail-berkeley/hil-serl) — 上层 Env/遥操作设计参考
- [LeRobot (HuggingFace)](https://github.com/huggingface/lerobot) — 数据格式
- [Franka Robotics 官方文档](https://frankarobotics.github.io/docs/overview.html)
- aiofranka 本地克隆：`/tmp/aiofranka_repo`

## 当前进度

所有 5 个 Phase 已完成：Gripper → Env → 遥操作/相机/数据采集 → 轨迹规划 → 双机 TCP 桥接。
7 个关键 BUG 已修复。Scripts 已从独立目录移入 `franka_control/scripts/`。

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

**文档：** `docs/env_design.md` 与实际实现偏差大（历史文档），`docs/implementation_plan.md` 进度未更新
