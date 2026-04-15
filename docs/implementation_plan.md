# Franka Control 实现计划

> **注意：这是初始实现计划，保留作为历史参考。**
> **文件路径和部分设计在实现过程中有调整，实际文件以 CLAUDE.md 为准。**

## 实现顺序

### Phase 1：控制机侧（基础设施） ✅

**1. Franka Gripper Server**
- 实际文件：`franka_control/gripper/gripper_server.py`（374 行）
- 实际实现：ZMQ ROUTER + 3 线程（主循环 / worker / 状态轮询）
- 序列化：msgpack（非 JSON）
- 客户端：`franka_control/gripper/gripper_client.py`（218 行）
- 入口：`franka_control/gripper/__main__.py`
- 测试：`tests/test_gripper.py`（23 tests）

### Phase 2：算法机侧（核心接口） ✅

**2. FrankaEnv**
- 实际文件：`franka_control/envs/franka_env.py`（511 行）
- 4 种 action_mode：`joint_abs` / `joint_delta` / `ee_abs` / `ee_delta`
- 2 种 gripper_mode：`continuous` / `binary`
- 延迟连接：`connect()` 方法，`__init__` 不触发硬件
- 物理单位：动作和观测均使用真实物理单位，无归一化

**3. 额外方法（实现时新增）**
- `move_to(qpos)`：阻塞式 Ruckig 移动
- `set_action_mode(mode)`：运行时热切换控制模式

**4. Safety Box Wrapper — 未实现**
- 安全限位内联在 `_clip_safety()` 中（仅关节限位）
- 笛卡尔空间裁剪待后续实现

### Phase 3：遥操作与数据 ✅

**5. SpaceMouse 遥操作**
- 实际文件：`franka_control/teleop/spacemouse_teleop.py`（241 行）
- 后台进程轮询 SpaceMouse Compact
- `get_action()`（纯遥操作）+ `maybe_override()`（HG-DAgger 干预）

**6. 数据采集器**
- 实际文件：`franka_control/data/collector.py`（255 行）
- LeRobot v3.0 格式（Parquet + MP4）
- 28D 状态向量 + 7D effort + 7D action

**相机管理（计划外新增）**
- `franka_control/cameras/camera_manager.py`（240 行）
- 多 RealSense 相机，每相机独立线程

### Phase 4：轨迹规划 ✅

**7. Waypoint 采集**
- 实际文件：`scripts/collect_waypoints.py`（362 行）
- 交互式 SpaceMouse 控制 + 键盘命令
- YAML 持久化：`franka_control/trajectory/waypoints.py`（191 行）

**8. TOPPRA 轨迹规划器**
- 实际文件：`franka_control/trajectory/planner.py`（443 行）
- 弦长参数化 + TOPPRA 时间最优 + rest-to-rest
- 约束：aiofranka 参数 80%
- `split_route()` 在夹爪动作点拆分路径

**9. 轨迹执行器**
- `execute_trajectory()`：基于 perf_counter 的逐点发送
- `execute_route()`：完整的 split → plan → execute 流程
- CLI：`scripts/run_trajectory.py`（204 行）

---

## 当前状态

- ✅ 需求讨论与确认
- ✅ 参考仓库深度分析
- ✅ 架构方案确认
- ✅ aiofranka API 研究
- ✅ 主流 Env 设计研究
- ✅ Env 设计方案完成
- ✅ **Phase 1：Franka Gripper Server**
- ✅ **Phase 2：FrankaEnv（4 模式 + move_to + set_action_mode）**
- ✅ **Phase 3：SpaceMouse 遥操作 + 相机 + 数据采集器**
- ✅ **Phase 4：Waypoint + TOPPRA 规划 + 执行**

---

## Phase 1 详细计划（历史）

### 目标
实现一个独立的 Franka 夹爪 ZMQ 服务器，验证通信链路。

### 技术栈
- pylibfranka.Gripper（Franka 官方 Python 绑定）
- ZMQ ROUTER/DEALER（实际实现，非原计划的 REQ/REP）
- msgpack 序列化（实际实现，非原计划的 JSON）

### 接口设计

**命令格式**（msgpack）：
```
open:     {"command": "open", "width": 0.08, "speed": 0.1}
grasp:    {"command": "grasp", "width": 0.02, "force": 40.0, "speed": 0.1, ...}
get_state: {"command": "get_state"}
stop:     {"command": "stop"}
homing:   {"command": "homing"}
shutdown: {"command": "shutdown"}
```

**响应格式**：
```
成功: {"success": true, "state": {...}}
失败: {"success": false, "error": "..."}
```
