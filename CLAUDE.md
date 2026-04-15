# Franka Control 项目

## 项目概述

从零构建一个用户完全清楚每一处细节的 Franka Research 3 机械臂控制库。用户负责架构和规划设计，Claude Code 负责执行实现。目标开源，供自己和他人通用使用。

## 协作方式（黄金法则）

### 1. 用户是大脑，Claude Code 是双手
永远不要全权委托。用户负责想清楚要做什么、怎么做，Claude Code 负责执行。不需要用户会写代码，但必须理解架构和每个模块的职责。

### 2. 先规划，后编码
任何任务开始前，先只出方案不写代码。用户审查、修改、确认方案后，再动手编码。

### 3. 一次只做一件小事
把大任务拆成小步骤，每步完成后用户亲自运行验证，确认没问题再进入下一步。绝不一口气做完整个功能。

### 4. 维护 CLAUDE.md
在项目根目录维护这份文档，写清楚项目概述、架构、当前进度、已知问题和约束。这是 Claude Code 的持久记忆。

### 5. Debug 时先问为什么，再问怎么修
遇到报错，不要直接粘贴让它改。先让它解释根本原因，给出多个可能性，用户判断后再让它修。

### 6. 定期清理，拒绝膨胀
每完成一个阶段，审查代码库，清除死代码、重复代码和临时补丁。保持仓库干净。

### 7. 让 Claude Code 教你
不懂的地方直接问解释。在理解上花的时间，会在后续节省 10 倍的 token 和调试时间。

---

## 已确认需求

### 使用场景
- **RL 训练**、**模仿学习**、**VLA**：通过 Gymnasium 风格 Env 接口（`reset()`/`step()`/`get_observation()`）
- **传统运动规划**：在遥操作采集的 waypoint 间执行轨迹（样条曲线 + TOPPRA/Ruckig 时间参数化），要求在每个点精确经过并在 endpoint 停止
- **遥操作**：键盘、SpaceMouse Compact（3Dconnexion），用于采集示教数据和 waypoint

### 硬件
- **机器人**：Franka Research 3（单台，不考虑多机）
- **夹爪**：Franka 自带夹爪
- **控制机**：Ubuntu 24，实时内核（PREEMPT_RT）
- **算法机**：通过 ZMQ 向控制机发送目标

### 双主机架构
- **算法机**：发送低频目标（1-200Hz），Python，通过 TCP ZMQ 与控制机通信
- **控制机**：1kHz FCI 实时控制循环，运行 RobotServer + GripperServer
- **通信**：TCP ZMQ + msgpack，独立端口（RobotServer 5555, GripperServer 5556）
- **同一仓库**：算法机和控制机共用一个代码仓库

### 控制模式（优先级从高到低）
1. Cartesian position
2. Joint position
3. Cartesian velocity
4. Joint velocity
5. 阻抗控制 / 力控（后续，需要学习）

### Env 接口设计
- **`reset()`**：清除错误（`automaticErrorRecovery`），机器人自动回到 home 位置
- **`step(action)`**：
  - action 空间可配置为**绝对目标**或**增量（delta）**模式
  - episode 终止条件：待定
- **`get_observation()`**：全量提供、按需选用
  - 关节位置、关节速度、关节力矩
  - 末端位姿（位置+姿态）、末端速度
  - 夹爪状态
  - 力/力矩传感器数据
  - 图像在算法机本地采集，不经过控制机

### 示教数据
- 存储格式：偏通用，可能采用 LeRobot 格式
- 存储内容：关节角、末端位姿、相机图像、夹爪状态、时间戳
- 主要用于训练，也可回放

### 安装与分发
- 当前阶段保持仓库结构，功能收尾后再考虑 pip 打包
- 不考虑仿真环境，专注真机

---

## 最终架构方案（已确认）

```
算法机 (GPU, Python):
├── Gym Env (借鉴 serl_robot_infra 设计) + Wrappers + Safety Box
├── 轨迹规划器 (样条 + TOPPRA, 关节空间, 用 aiofranka 参数的 80%)
├── 数据采集器 (LeRobot 格式)
└── SpaceMouse 遥操作 (复用 serl 代码)
    ↕ TCP ZMQ (msgpack 序列化)
控制机 (RT kernel):
├── RobotServer (TCP 5555, 包装 FrankaRemoteController)
│   └─ aiofranka 子进程 (IPC + SharedMemory)
├── GripperServer (TCP 5556, pylibfranka.Gripper)
└── Franka Research 3
```

### 关键设计决策
- **底层**：aiofranka 不修改，固定在控制机上，通过 RobotServer TCP 桥接暴露
- **上层**：借鉴 serl_robot_infra 的设计模式（Gym Env、遥操作），重新实现
- **轨迹规划**：算法机离线规划（样条+TOPPRA），采样后逐点 `env.step()` 执行
- **夹爪**：独立进程 + ZMQ（aiofranka 的 GripperController 是 Robotiq，需新建 Franka Gripper 版本）
- **Safety Box**：Gym 层 `clip_safety_box()`
- **单档参数**：不需要两级阻抗参数
- **远距离目标安全**：aiofranka PID/OSC 不会 abort，力矩 clip 后平滑追踪
- **统一接口**：RL/遥操作/轨迹执行/回放 全部走 `env.step(action)`

### TOPPRA 轨迹规划
- waypoint 通过遥操作采集（home, above_basket 等关键点）
- 样条插值生成几何路径 → TOPPRA 时间参数化 → 采样成高频点
- 约束：aiofranka 参数的 80%（vel=8 rad/s, acc=4 rad/s²）
- 关节空间规划，Joint PID 执行

### aiofranka 核心 API（实现参考）
- **FrankaRemoteController**：同步远程控制器（控制机本地使用，被 RobotServer 包装）
  - `start()` / `stop()`：启动/停止
  - `switch(type)`：切换控制模式（impedance/pid/osc/torque）
  - `set(attr, value)`：设置目标（q_desired / ee_desired / torque）
  - `move(qpos)`：Ruckig 轨迹移动（阻塞）
  - `.state`：读取完整状态（qpos/qvel/ee/jac/mm/last_torque）
- **RobotServer**：TCP 桥接（控制机运行），3 线程（主循环/worker/状态轮询）
- **RobotClient**：算法机 TCP 客户端，API 与 FrankaRemoteController 一致
- **ZMQ 协议**：TCP ROUTER/DEALER，msgpack 序列化，端口 5555
- **安全参数**：力矩限制 [87,87,87,87,12,12,12] Nm，速率限制 990 Nm/s

---

## 参考库

- [Franka Robotics 官方文档](https://frankarobotics.github.io/docs/overview.html)
- [serl_franka_controllers (RAIL Berkeley)](https://github.com/rail-berkeley/serl_franka_controllers)
- [franky (TimSchneider42)](https://github.com/TimSchneider42/franky)
- [aiofranka (Improbable-AI)](https://github.com/Improbable-AI/aiofranka)
- [serl_robot_infra (HIL-SERL)](https://github.com/rail-berkeley/hil-serl) — 上层设计参考
- [OpenPI (Physical Intelligence)](https://github.com/Physical-Intelligence/openpi)
- [Octo (UC Berkeley)](https://github.com/octo-model/octo)
- [LeRobot (HuggingFace)](https://github.com/huggingface/lerobot)
- [Diffusion Policy (Stanford)](https://github.com/real-stanford/diffusion_policy)
- aiofranka 本地克隆：`/tmp/aiofranka_repo`

---

## 当前进度

### 已完成
- ✅ 需求讨论与确认
- ✅ 6+ 参考仓库深度分析（报告写入 Notion）
- ✅ 架构方案讨论与最终确认
- ✅ aiofranka API 接口研究
- ✅ 主流 Env 设计研究（OpenPI/Octo/LeRobot/Diffusion Policy）
- ✅ Env 设计方案完成 → `docs/env_design.md`（历史设计文档，实际实现有偏差）
- ✅ 实现计划制定 → `docs/implementation_plan.md`
- ✅ **Phase 1：Franka Gripper Server** — `franka_control/gripper/`
  - `gripper_server.py`：ZMQ ROUTER + 3 线程（主循环/worker/状态轮询）
  - `gripper_client.py`：ZMQ DEALER + 阻塞 API
  - `__main__.py`：`python -m franka_control.gripper` 入口
  - 测试：`tests/test_gripper.py`（23 tests）
- ✅ **Phase 2：FrankaEnv** — `franka_control/envs/franka_env.py`
  - 4 种 action_mode：joint_abs / joint_delta / ee_abs / ee_delta
  - 2 种 gripper_mode：continuous / binary
  - `move_to(qpos)`：阻塞 Ruckig 移动
  - `set_action_mode(mode)`：运行时热切换
- ✅ **Phase 3：遥操作与数据**
  - `franka_control/teleop/spacemouse_teleop.py`：SpaceMouse Compact，后台进程轮询
  - `franka_control/cameras/camera_manager.py`：多 RealSense 相机管理
  - `franka_control/data/collector.py`：LeRobot v3.0 格式数据采集
  - `scripts/teleop.py`：遥操作脚本
  - `scripts/collect_data.py`：数据采集脚本
- ✅ **Phase 4：轨迹规划** — `franka_control/trajectory/`
  - `waypoints.py`：WaypointStore（YAML 持久化 + CRUD）
  - `planner.py`：TOPPRA 时间最优轨迹规划 + 执行
  - `scripts/collect_waypoints.py`：交互式 waypoint 采集
  - `scripts/run_trajectory.py`：轨迹执行 CLI
- ✅ **Phase 5：双机 TCP 桥接** — `franka_control/robot/`
  - `robot_server.py`：RobotServer（TCP 5555），包装 FrankaRemoteController，3 线程
  - `robot_client.py`：RobotClient，算法机 TCP 客户端，API 与 FrankaRemoteController 一致
  - `FrankaEnv` 已改为通过 RobotClient 通信，不再依赖 aiofranka
  - 所有 scripts 已添加 `--fci-ip` 参数
- ✅ **全仓库代码审查**：7 BUG 已全部修复
- ✅ **Scripts 重构**：从独立目录移入 `franka_control/scripts/`

### 已知问题（已修复 BUG #1-7）

7 个 BUG 已全部修复。中等问题（8-18）为非关键优化，暂未处理。

**中等问题（8-18）：**
8-10. gripper_server 参数校验、stop 结果重置、轮询退避
11-13. spacemouse 非原子读取、按钮假设、参数验证
14-15. camera_manager 关闭竞态、静默旧帧
16-17. collector gripper 填零、lerobot API 兼容
18. 常量重复定义

**文档（已过时）：**
- `docs/env_design.md` 与实际实现偏差大（标记为历史设计文档）
- `docs/implementation_plan.md` 进度未更新

### 待讨论 / 待研究（TBD）

- **安全限位策略**：关节限位、速度限制是否由库内部 clamp → 当前 `_clip_safety()` 只做关节限位
- **工作空间限制**：是否需要笛卡尔空间限制 → Safety Box Wrapper 未实现
- **碰撞检测**：是否需要自碰撞检测
- **episode 终止条件**：由谁决定 done → 当前始终返回 False

### 实现路线图

**Phase 1：控制机侧（基础设施）** ✅
1. Franka Gripper Server — `franka_control/gripper/`

**Phase 2：算法机侧（核心接口）** ✅
2. FrankaEnv — `franka_control/envs/franka_env.py`（4 模式 + move_to + set_action_mode）
3. Safety Box Wrapper — 未实现为独立 wrapper，`_clip_safety()` 内联在 env 中

**Phase 3：遥操作与数据** ✅
4. SpaceMouse 遥操作 — `franka_control/teleop/`
5. 相机管理 — `franka_control/cameras/`
6. 数据采集器 — `franka_control/data/`

**Phase 4：轨迹规划** ✅
7. Waypoint 采集 — `scripts/collect_waypoints.py`
8. TOPPRA 规划 + 执行 — `franka_control/trajectory/planner.py`
9. 执行脚本 — `scripts/run_trajectory.py`

**Phase 5：双机 TCP 桥接** ✅
10. RobotServer — `franka_control/robot/robot_server.py`
11. RobotClient — `franka_control/robot/robot_client.py`
12. FrankaEnv 改造 — 不再依赖 aiofranka，通过 RobotClient TCP 通信

详见 `docs/implementation_plan.md`
