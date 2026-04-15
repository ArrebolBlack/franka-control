# Phase 4 实现计划：轨迹规划（讨论稿）

## Context

Franka Research 3 的传统运动规划需求：通过遥操作采集关键点（waypoint），
用 TOPPRA 生成时间最优轨迹，逐点发送给机器人执行。

---

## 总体文件结构

```
franka_control/
├── trajectory/
│   ├── __init__.py
│   ├── waypoints.py       # WaypointStore
│   └── planner.py         # TrajectoryPlanner + Trajectory + execute_trajectory()
├── envs/
│   └── franka_env.py      # 新增 move_to() + set_action_mode() + gripper 直接控制
scripts/
├── collect_waypoints.py
└── run_trajectory.py
```

---

## 分段计划

### 段 1: FrankaEnv 修改
- move_to(qpos)
- set_action_mode(mode)
- gripper_open() / gripper_close()

### 段 2: WaypointStore
- 数据类 Waypoint + Route
- YAML 格式
- CRUD API

### 段 3: TrajectoryPlanner
- Trajectory 数据类
- TOPPRA 规划流程
- waypoint_indices（用序号不用名称）
- 静态安全检查

### 段 4: execute_trajectory()
- 执行循环
- 夹爪同步（直接调 gripper API，绕过防抖）

### 段 5: collect_waypoints.py
- 交互设计（raw/normal 终端切换）
- 控制键

### 段 6: run_trajectory.py
- 命令行参数
- 执行流程

---

## 待确认问题（用户已指出）→ 已解决

1. **waypoint_indices 不能用 name 做 key** → 已解决：使用 `list[int]`，长度 = route 中 waypoint 数量
2. **TOPPRA 中间点不停** → 已解决：通过 `split_route()` 在夹爪动作点拆分为独立段，每段 rest-to-rest
3. **夹爪事件要绕过 binary 防抖** → 已解决：简化设计，所有夹爪动作通过 `env.step()` 执行，利用 binary 模式的天然防抖。段间机器人停止后发送一步触发夹爪动作
