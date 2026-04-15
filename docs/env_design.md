# Franka Control Env 设计文档

> **注意：这是 Phase 2 开始前的设计文档，保留作为历史参考。**
> **实际实现有多处偏差，以下是与代码的主要差异：**
>
> | 设计文档 | 实际实现 |
> |---------|---------|
> | 观测空间嵌套 `{"state": {...}, "images": {...}}` | 扁平字典 `{"joint_pos", "joint_vel", "ee_pos", "ee_quat", "ee_vel", "joint_torque", "gripper_width"}` |
> | 动作空间归一化 `[-1, 1]` + action_scale | 物理单位（rad, m），`joint_delta` 范围 `[-0.1, 0.1]` |
> | `step()` 含频率控制 `time.sleep()` 和 `compute_reward()` | 无频率控制，始终返回 `reward=0.0, terminated=False, truncated=False` |
> | 夹爪用 `zmq.REQ` + JSON | 夹爪用 `zmq.DEALER/ROUTER` + msgpack |
> | `__init__` 中连接硬件 | `connect()` 延迟连接，`__init__` 不触发硬件 |
> | `gripper_pos` 范围 `[0, 1]` | `gripper_width` 范围 `[0, 0.08]` 米 |
> | SafetyBox 独立 wrapper | `_clip_safety()` 内联在 env 中，仅关节限位 |
> | 无 `move_to()` / `set_action_mode()` | 已实现（Phase 2 新增） |
> | 图像在 env 观测中 | 图像由独立 `CameraManager` 管理，不在 env 观测中 |

## 设计概览

基于对 serl_robot_infra、OpenPI、Octo、LeRobot、Diffusion Policy 的研究，采用以下设计方案：

- **底层**：aiofranka（不修改）
- **上层**：标准 Gym Env + 轻量 Wrapper
- **通信**：ZMQ（复用 aiofranka 协议）+ SharedMemory（状态读取）
- **夹爪**：独立 ZMQ 服务（新建，基于 pylibfranka.Gripper）

---

## 第一部分：Env 语义设计

### 1. 接口选择：标准 Gym

```python
class FrankaEnv(gym.Env):
    def reset(self, **kwargs) -> tuple[dict, dict]:
        """返回 (observation, info)"""

    def step(self, action: np.ndarray) -> tuple[dict, float, bool, bool, dict]:
        """返回 (observation, reward, terminated, truncated, info)"""

    def get_observation(self) -> dict:
        """显式获取观测（可选，用于高频读取）"""
```

**设计原则**：
- 兼容 Gym 生态（Stable-Baselines3、CleanRL 等）
- 借鉴 Octo 的简洁性 + LeRobot 的灵活性
- serl 也用标准 Gym，证明真机场景够用

### 2. 观测空间：分层字典 + 全量提供

```python
observation_space = gym.spaces.Dict({
    "state": gym.spaces.Dict({
        "joint_pos": Box(-2.9, 2.9, (7,), float32),      # 关节位置 [rad]
        "joint_vel": Box(-2.6, 2.6, (7,), float32),      # 关节速度 [rad/s]
        "ee_pos": Box(-1, 1, (3,), float32),             # 末端位置 [m]
        "ee_quat": Box(-1, 1, (4,), float32),            # 末端姿态（四元数）
        "ee_vel": Box(-2, 2, (6,), float32),             # 末端速度（空间速度）
        "gripper_pos": Box(0, 1, (1,), float32),         # 夹爪开合度 [0=关, 1=开]
    }),
    "images": gym.spaces.Dict({
        "wrist": Box(0, 255, (H, W, 3), uint8),
        "front": Box(0, 255, (H, W, 3), uint8),
        # 相机名称可配置
    }),
})
```

**设计原则**（借鉴 LeRobot）：
- 全量提供，按需选用（通过 Wrapper 过滤）
- 图像在算法机本地采集，不经过控制机
- 末端位姿用四元数（避免欧拉角奇异），可通过 Wrapper 转换

### 3. 动作空间：可配置模式

```python
# 配置项
action_mode: Literal["joint_abs", "joint_delta", "ee_abs", "ee_delta"]
include_gripper: bool = True

# 动作空间根据配置动态生成
if action_mode == "joint_delta":
    action_space = Box(-0.05, 0.05, (7 + int(include_gripper),), float32)
elif action_mode == "ee_delta":
    action_space = Box(-1, 1, (6 + int(include_gripper),), float32)  # xyz + rotvec
```

**为什么支持多种模式？**
- RL 训练常用 delta（更平滑）
- 轨迹执行用 abs（精确）
- serl 只支持 ee_delta，但我们需求包含关节空间控制

### 4. reset() 语义：清除错误 + 回 home

```python
def reset(self, joint_reset: bool = False, **kwargs):
    # 1. 停止当前控制（aiofranka controller.stop()）
    # 2. 清除错误（aiofranka 自动 error recovery）
    # 3. 回 home（controller.move(HOME_QPOS)，Ruckig 轨迹）
    # 4. 可选：周期性关节复位（借鉴 serl）
    # 5. 重启控制循环（controller.start()）
    # 6. 返回初始观测
    return self.get_observation(), {"succeed": False}
```

### 5. step() 语义：频率控制 + Safety Box

```python
def step(self, action: np.ndarray):
    start_time = time.time()

    # 1. clip 动作到 [-1, 1]
    action = np.clip(action, -1, 1)

    # 2. 解析动作（关节/末端，绝对/增量）
    target = self._parse_action(action)

    # 3. Safety Box clip（借鉴 serl）
    target = self._clip_safety_box(target)

    # 4. 发送目标到 aiofranka
    self.controller.set("q_desired", target)  # 或 "ee_desired"

    # 5. 发送夹爪指令（二值模式，防抖）
    self._send_gripper_command(action[-1])

    # 6. 频率控制 sleep
    time.sleep(max(0, 1/self.hz - (time.time() - start_time)))

    # 7. 读取状态
    obs = self.get_observation()

    # 8. 计算奖励和终止
    reward = self.compute_reward(obs)
    done = (self.step_count >= self.max_episode_length) or reward

    return obs, reward, done, False, {"succeed": reward}
```

---

## 第二部分：aiofranka 精确实现

### 1. 初始化：连接 aiofranka server

```python
class FrankaEnv(gym.Env):
    def __init__(self, robot_ip: str, hz: float = 50, ...):
        # 启动 aiofranka server（如果未运行）
        aiofranka.start(robot_ip, unlock=True)

        # 创建远程控制器
        self.controller = FrankaRemoteController(robot_ip)
        self.controller.start()

        # 切换控制模式（默认 PID）
        self.controller.switch("pid")

        # 设置增益（可配置）
        self.controller.kp = np.array([80, 80, 80, 80, 40, 40, 40])
        self.controller.kd = np.array([4, 4, 4, 4, 2, 2, 2])
```

### 2. reset() 实现

```python
def reset(self, joint_reset: bool = False, **kwargs):
    # 停止控制循环
    self.controller.stop()

    # aiofranka 自动 error recovery（内置）

    # 回 home（Ruckig 轨迹，阻塞）
    self.controller.move(self.HOME_QPOS)

    # 重启控制循环
    self.controller.start()

    # 重置计数器
    self.step_count = 0

    return self.get_observation(), {}
```

### 3. get_observation() 实现

```python
def get_observation(self) -> dict:
    # 从 aiofranka 读取状态（SharedMemory，零拷贝）
    state = self.controller.state

    # 从本地相机读取图像
    images = self._capture_images()

    return {
        "state": {
            "joint_pos": state["qpos"].astype(np.float32),
            "joint_vel": state["qvel"].astype(np.float32),
            "ee_pos": state["ee"][:3, 3].astype(np.float32),
            "ee_quat": Rotation.from_matrix(state["ee"][:3, :3]).as_quat().astype(np.float32),
            "ee_vel": (state["jac"] @ state["qvel"]).astype(np.float32),
            "gripper_pos": np.array([self.gripper.get_state()], dtype=np.float32),
        },
        "images": images,
    }
```

### 4. step() 中的目标发送

```python
def _send_target(self, action: np.ndarray):
    if self.action_mode == "joint_delta":
        # 增量模式：叠加到当前位置
        current_q = self.controller.state["qpos"]
        target_q = current_q + action[:7] * self.action_scale
        self.controller.set("q_desired", target_q)

    elif self.action_mode == "joint_abs":
        # 绝对模式：直接设置
        self.controller.set("q_desired", action[:7])

    elif self.action_mode == "ee_delta":
        # 末端增量：需要转换
        current_ee = self.controller.state["ee"]
        delta_pos = action[:3] * self.action_scale[0]
        delta_rot = Rotation.from_rotvec(action[3:6] * self.action_scale[1])
        target_ee = self._apply_ee_delta(current_ee, delta_pos, delta_rot)
        self.controller.set("ee_desired", target_ee)
```

### 5. 夹爪控制

```python
# 独立进程 + ZMQ（参考 serl）
class FrankaGripperClient:
    def __init__(self, gripper_ip: str):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REQ)
        self.socket.connect(f"tcp://{gripper_ip}:5556")

    def open(self):
        self.socket.send_json({"command": "open"})
        self.socket.recv_json()

    def close(self):
        self.socket.send_json({"command": "close"})
        self.socket.recv_json()

    def get_state(self) -> float:
        self.socket.send_json({"command": "get_state"})
        return self.socket.recv_json()["position"]
```

### 6. Safety Box

```python
def _clip_safety_box(self, target: np.ndarray) -> np.ndarray:
    if self.action_mode.startswith("joint"):
        # 关节限位（Franka 官方限制）
        return np.clip(target, self.JOINT_LIMIT_LOW, self.JOINT_LIMIT_HIGH)

    elif self.action_mode.startswith("ee"):
        # 笛卡尔限位（借鉴 serl 的 clip_safety_box）
        target[:3] = np.clip(target[:3], self.EE_POS_LOW, self.EE_POS_HIGH)
        # 姿态限制（可选）
        return target
```

---

## 实现顺序

### Phase 1：控制机侧（基础设施）
1. **Franka Gripper Server** — aiofranka 的夹爪是 Robotiq 的，我们需要新建一个 pylibfranka.Gripper 的 ZMQ 服务端。这是独立模块，最简单，适合先做起来验证通信链路。

### Phase 2：算法机侧（核心接口）
2. **Gym Env 基础版** — 包装 FrankaRemoteController，实现 reset() / step() / get_observation() / close()。先只支持 Joint Position（impedance 模式），跑通最小闭环。
3. **多控制模式支持** — 在 Env 基础上加 Cartesian Position（OSC）、velocity 模式、delta/absolute 切换。
4. **Safety Box Wrapper** — Gym wrapper 层的笛卡尔空间裁剪。

### Phase 3：遥操作与数据
5. **SpaceMouse 遥操作** — 复用 serl/aiofranka 的 SpaceMouse 代码，作为 action provider 接入 Env。
6. **数据采集器** — LeRobot 格式，在 env.step() 循环中记录 observation + action。

### Phase 4：轨迹规划
7. **Waypoint 采集工具** — 遥操作模式下记录关键点。
8. **TOPPRA 轨迹规划器** — 样条插值 + TOPPRA 时间参数化，输出采样点序列。
9. **轨迹执行器** — 读取规划结果，逐点 env.step() 执行。

---

## 设计总结

| 功能 | 语义来源 | 实现来源 |
|------|---------|---------|
| **接口** | Gym 标准（Octo/LeRobot） | `gym.Env` |
| **观测空间** | 分层字典（LeRobot） | `aiofranka controller.state` + 本地相机 |
| **动作空间** | 可配置模式（LeRobot） | `controller.set()` |
| **reset()** | 清除错误+回home（serl） | `controller.move()` |
| **step()** | 频率控制+Safety Box（serl） | `controller.set()` + `time.sleep()` |
| **夹爪** | 二值控制（serl） | 独立 ZMQ 客户端 |
| **Wrappers** | 历史堆叠/归一化（Octo） | 标准 Gym Wrapper |

---

## 参考资料

- aiofranka API 研究：已完成，见 subagent 输出
- serl_robot_infra Env 设计：已完成，见 subagent 输出
- OpenPI/Octo/LeRobot/Diffusion Policy 对比：已完成，见 subagent 输出
