"""Franka Gym Environment.

Dual-machine architecture: algorithm machine (this code) communicates with
control machine via TCP. Robot control via RobotClient (ZMQ → RobotServer
→ aiofranka), gripper via GripperClient (ZMQ → GripperServer → pylibfranka).

Standard Gymnasium interface: reset() / step() / get_observation() / close().

Actions and observations use REAL PHYSICAL UNITS (no normalization).
For RL training, add a NormalizeActionWrapper externally.

Does NOT manage frequency, reward, or episode length — those are the
caller's responsibility (or add wrappers like TimeLimit).

Usage:
    env = FrankaEnv(robot_ip="192.168.0.2",
                    action_mode="joint_delta", gripper_mode="continuous")
    obs, _ = env.reset()
    action = policy(obs)
    obs, reward, done, truncated, info = env.step(action)
    env.close()
"""

from __future__ import annotations

import logging
import time
from typing import Optional

import gymnasium as gym
import numpy as np
from scipy.spatial.transform import Rotation

from franka_control.gripper.gripper_client import GripperClient
from franka_control.robot.robot_client import RobotClient

logger = logging.getLogger(__name__)


# ── Constants ────────────────────────────────────────────────────

# Franka Research 3 home position [rad]
DEFAULT_HOME_QPOS = np.array(
    [0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785],
    dtype=np.float64,
)

# Franka Research 3 joint limits [rad]
# Source: https://frankaemika.github.io/docs/control_parameters.html
JOINT_LIMIT_LOW = np.array(
    [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973]
)
JOINT_LIMIT_HIGH = np.array(
    [2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973]
)

# joint_delta bounds [rad]: ±0.1 rad ≈ ±5.7° per step
JOINT_DELTA_LIMIT = np.full(7, 0.1)

# ee_abs bounds: position [m] + rotation [rad]
# Position: conservative workspace (Franka reach ~0.855m)
# Rotation: full ±2π
EE_ABS_LOW = np.array([-0.8, -0.8, 0.0, -2 * np.pi, -2 * np.pi, -2 * np.pi])
EE_ABS_HIGH = np.array([0.8, 0.8, 1.2, 2 * np.pi, 2 * np.pi, 2 * np.pi])

# ee_delta bounds: position [m] + rotation [rad]
EE_DELTA_LIMIT = np.array([0.05, 0.05, 0.05, 0.3, 0.3, 0.3])

# Gripper defaults
GRIPPER_SLEEP = 0.6       # binary mode debounce [s]
GRIPPER_SPEED = 0.1       # fixed speed [m/s]
GRIPPER_FORCE = 40.0      # default grasp force [N]
GRIPPER_MAX_WIDTH = 0.08  # max width [m]
GRIPPER_THRESHOLD = 0.5   # binary mode threshold


class FrankaEnv(gym.Env):
    """Franka Research 3 Gym Environment.

    Dual-machine architecture: communicates with RobotServer on control
    machine via TCP ZMQ. No direct aiofranka dependency.

    Actions and observations use real physical units.
    No normalization, no frequency control, no reward computation.

    Args:
        robot_ip: Control machine IP (RobotServer and GripperServer address).
        robot_port: RobotServer ZMQ port (default: 5555).
        gripper_host: Gripper server host (None = no gripper).
        gripper_port: Gripper server ZMQ port.
        action_mode: One of joint_abs, joint_delta, ee_abs, ee_delta.
        gripper_mode: continuous or binary (only when gripper_host is set).
        home_qpos: Home joint position for reset [rad].
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        robot_ip: str,
        robot_port: int = 5555,
        gripper_host: Optional[str] = None,
        gripper_port: int = 5556,
        action_mode: str = "joint_abs",
        gripper_mode: str = "continuous",
        grasp_force: float = GRIPPER_FORCE,
        home_qpos: np.ndarray = None,
    ):
        super().__init__()

        # Validate params
        valid_action_modes = {"joint_abs", "joint_delta", "ee_abs", "ee_delta"}
        if action_mode not in valid_action_modes:
            raise ValueError(
                f"action_mode must be one of {valid_action_modes}, "
                f"got '{action_mode}'"
            )
        self.action_mode = action_mode
        self.use_gripper = gripper_host is not None
        self.gripper_mode = gripper_mode
        self._grasp_force = grasp_force
        self.home_qpos = (
            home_qpos if home_qpos is not None else DEFAULT_HOME_QPOS.copy()
        )

        # ── Action space (physical units) ────────────────────────
        self._robot_action_dim = 7 if action_mode.startswith("joint") else 6
        total_dim = self._robot_action_dim + (1 if self.use_gripper else 0)

        robot_low, robot_high = self._get_robot_action_bounds()
        gripper_low, gripper_high = self._get_gripper_action_bounds()

        low = np.concatenate([robot_low, gripper_low])
        high = np.concatenate([robot_high, gripper_high])
        self.action_space = gym.spaces.Box(
            low=low, high=high, dtype=np.float32
        )

        # ── Observation space (physical units) ───────────────────
        obs_spaces = {
            "joint_pos": gym.spaces.Box(
                -np.inf, np.inf, shape=(7,), dtype=np.float32
            ),
            "joint_vel": gym.spaces.Box(
                -np.inf, np.inf, shape=(7,), dtype=np.float32
            ),
            "ee_pos": gym.spaces.Box(
                -np.inf, np.inf, shape=(3,), dtype=np.float32
            ),
            "ee_quat": gym.spaces.Box(
                -1, 1, shape=(4,), dtype=np.float32
            ),
            "ee_vel": gym.spaces.Box(
                -np.inf, np.inf, shape=(6,), dtype=np.float32
            ),
            "joint_torque": gym.spaces.Box(
                -np.inf, np.inf, shape=(7,), dtype=np.float32
            ),
        }
        if self.use_gripper:
            obs_spaces["gripper_width"] = gym.spaces.Box(
                0, GRIPPER_MAX_WIDTH, shape=(1,), dtype=np.float32
            )
        self.observation_space = gym.spaces.Dict(obs_spaces)

        # ── Robot connection ─────────────────────────────────────
        self.robot_ip = robot_ip
        self._robot_port = robot_port
        self._robot: Optional[RobotClient] = None

        # ── Gripper connection ───────────────────────────────────
        self._gripper: Optional[GripperClient] = None
        self._gripper_host = gripper_host
        self._gripper_port = gripper_port
        self._last_gripper_time = 0.0
        self._last_gripper_command: Optional[str] = None
        self._gripper_max_width = GRIPPER_MAX_WIDTH

        # ── State cache ──────────────────────────────────────────
        self._current_qpos = np.zeros(7, dtype=np.float64)
        self._current_ee = np.eye(4, dtype=np.float64)

    # ── Action bounds helpers ─────────────────────────────────────

    def _get_robot_action_bounds(self):
        """Return (low, high) arrays for robot action dimensions."""
        if self.action_mode == "joint_abs":
            return JOINT_LIMIT_LOW, JOINT_LIMIT_HIGH
        elif self.action_mode == "joint_delta":
            return -JOINT_DELTA_LIMIT, JOINT_DELTA_LIMIT
        elif self.action_mode == "ee_abs":
            return EE_ABS_LOW, EE_ABS_HIGH
        elif self.action_mode == "ee_delta":
            return -EE_DELTA_LIMIT, EE_DELTA_LIMIT

    def _get_gripper_action_bounds(self):
        """Return (low, high) arrays for gripper action dimension."""
        if not self.use_gripper:
            return np.array([]), np.array([])
        if self.gripper_mode == "continuous":
            return np.array([0.0]), np.array([GRIPPER_MAX_WIDTH])
        else:  # binary
            return np.array([0.0]), np.array([1.0])

    # ── Lifecycle ────────────────────────────────────────────────

    def connect(self) -> None:
        """Connect to robot and gripper servers.

        Call this before reset() or step(). Not in __init__ so that
        gym.make() doesn't trigger hardware connection.
        """
        logger.info("Connecting to robot server at %s:%d ...",
                     self.robot_ip, self._robot_port)
        self._robot = RobotClient(
            host=self.robot_ip, port=self._robot_port,
        )

        # Determine initial controller type
        ctrl_type = "pid" if self.action_mode.startswith("joint") else "osc"
        if not self._robot.connect(controller_type=ctrl_type):
            raise RuntimeError("Failed to connect to robot")
        logger.info("Robot connected. Mode: %s", self.action_mode)

        # Gripper
        if self.use_gripper:
            logger.info("Connecting to gripper at %s:%d ...",
                        self._gripper_host, self._gripper_port)
            self._gripper = GripperClient(
                self._gripper_host, self._gripper_port
            )
            self._gripper.homing()
            state = self._gripper.get_state()
            if state:
                self._gripper_max_width = state.get("max_width", GRIPPER_MAX_WIDTH)
            logger.info("Gripper connected. Max width: %.4f m",
                        self._gripper_max_width)

        # Cache initial state
        self._update_current_state()

    # ── Gym interface ────────────────────────────────────────────

    def reset(self, *, seed=None, options=None):
        """Reset environment: move to home, open gripper.

        Returns:
            (observation, info)
        """
        super().reset(seed=seed)

        if self._robot is None:
            self.connect()

        # Stop → move home → restart
        self._robot_call(self._robot.stop, "stop")
        self._robot_call(lambda: self._robot.move(self.home_qpos), "move home")
        self._robot_call(self._robot.start, "start")

        # Re-switch controller (stop/start may reset)
        if self.action_mode.startswith("joint"):
            self._robot_call(lambda: self._robot.switch("pid"), "switch pid")
        else:
            self._robot_call(lambda: self._robot.switch("osc"), "switch osc")

        # Open gripper
        if self.use_gripper and self._gripper:
            self._gripper.open(width=self._gripper_max_width)
            self._last_gripper_command = "open"
            self._last_gripper_time = time.time()

        self._update_current_state()
        return self.get_observation(), {}

    def step(self, action: np.ndarray):
        """Execute one step.

        Args:
            action: Physical-unit action array.
                Robot part: see action_space bounds (rad, m, etc.)
                Gripper part: [0, max_width] or [0, 1] depending on mode

        Returns:
            (observation, reward, terminated, truncated, info)
        """
        action = np.clip(action, self.action_space.low, self.action_space.high)

        # Split robot and gripper actions
        robot_action = action[: self._robot_action_dim]
        gripper_action = action[self._robot_action_dim] if self.use_gripper else None

        # Convert action to target
        target = self._parse_action(robot_action)

        # Safety clip
        target = self._clip_safety(target)

        # Send to robot
        self._send_target(target)

        # Handle gripper
        if gripper_action is not None:
            self._handle_gripper(gripper_action)

        # Read state
        self._update_current_state()
        obs = self.get_observation()

        return obs, 0.0, False, False, {}

    def get_observation(self) -> dict:
        """Read current observation from RobotClient state cache."""
        if self._robot is None:
            raise RuntimeError("Not connected. Call connect() or reset() first.")

        state = self._robot.state

        obs = {
            "joint_pos": state["qpos"].astype(np.float32),
            "joint_vel": state["qvel"].astype(np.float32),
            "joint_torque": state["last_torque"].astype(np.float32),
            "ee_pos": state["ee"][:3, 3].astype(np.float32),
            "ee_quat": Rotation.from_matrix(state["ee"][:3, :3])
            .as_quat()
            .astype(np.float32),
            "ee_vel": (state["jac"] @ state["qvel"]).astype(np.float32),
        }

        if self.use_gripper and self._gripper:
            gripper_state = self._gripper.get_state()
            width = gripper_state["width"] if gripper_state else 0.0
            obs["gripper_width"] = np.array([width], dtype=np.float32)

        return obs

    def close(self):
        """Disconnect from robot and gripper."""
        if self._robot is not None:
            try:
                self._robot.close()
            except Exception as e:
                logger.warning("Error closing robot client: %s", e)
            self._robot = None

        if self._gripper is not None:
            try:
                self._gripper.close()
            except Exception as e:
                logger.warning("Error closing gripper: %s", e)
            self._gripper = None

        logger.info("FrankaEnv closed.")

    # ── Utility ──────────────────────────────────────────────────

    def move_to(self, qpos: np.ndarray) -> None:
        """Blocking Ruckig move to target joint position.

        Temporarily switches to PID mode, executes move, then restores
        the previous controller type. Does NOT change self.action_mode.

        Args:
            qpos: Target joint angles [rad], shape (7,).
        """
        if self._robot is None:
            raise RuntimeError("Not connected. Call connect() or reset() first.")
        prev_was_joint = self.action_mode.startswith("joint")
        self._robot_call(self._robot.stop, "stop")
        self._robot_call(lambda: self._robot.switch("pid"), "switch pid")
        try:
            target = np.clip(qpos, JOINT_LIMIT_LOW, JOINT_LIMIT_HIGH)
            self._robot_call(lambda: self._robot.move(target), "move")
        finally:
            # Always restore controller, even if move() failed
            self._robot_call(self._robot.start, "start")
            if not prev_was_joint:
                self._robot_call(lambda: self._robot.switch("osc"), "switch osc")
        self._update_current_state()

    def set_action_mode(self, mode: str) -> None:
        """Switch control mode at runtime (hot-swap).

        Changes action_mode, rebuilds action_space, and switches the
        underlying controller (PID/OSC). No stop/start needed.

        Args:
            mode: One of joint_abs, joint_delta, ee_abs, ee_delta.
        """
        valid = {"joint_abs", "joint_delta", "ee_abs", "ee_delta"}
        if mode not in valid:
            raise ValueError(
                f"action_mode must be one of {valid}, got '{mode}'"
            )
        if self._robot is None:
            raise RuntimeError("Not connected. Call connect() or reset() first.")

        # Remote switch first — if this fails, local state is untouched
        if mode.startswith("joint"):
            self._robot_call(lambda: self._robot.switch("pid"), "switch pid")
        else:
            self._robot_call(lambda: self._robot.switch("osc"), "switch osc")

        # Remote succeeded — now update local state
        self.action_mode = mode
        self._robot_action_dim = 7 if mode.startswith("joint") else 6

        robot_low, robot_high = self._get_robot_action_bounds()
        gripper_low, gripper_high = self._get_gripper_action_bounds()
        self.action_space = gym.spaces.Box(
            low=np.concatenate([robot_low, gripper_low]),
            high=np.concatenate([robot_high, gripper_high]),
            dtype=np.float32,
        )

        logger.info("Action mode switched to: %s", mode)

    # ── Action parsing ───────────────────────────────────────────

    def _parse_action(self, action: np.ndarray):
        """Convert physical-unit action to controller target.

        Returns:
            np.ndarray [7] for joint modes (joint angles),
            np.ndarray [4x4] for ee modes (homogeneous matrix).
        """
        if self.action_mode == "joint_abs":
            # action is already in [rad]
            return action.astype(np.float64)

        elif self.action_mode == "joint_delta":
            # action is delta in [rad], add to current
            return self._current_qpos + action

        elif self.action_mode == "ee_abs":
            # action = [xyz(3), rotvec(3)] → 4x4 matrix
            target = np.eye(4)
            target[:3, 3] = action[:3]
            target[:3, :3] = Rotation.from_rotvec(action[3:]).as_matrix()
            return target

        elif self.action_mode == "ee_delta":
            # action = [delta_xyz(3), delta_rotvec(3)]
            target = self._current_ee.copy()
            target[:3, 3] += action[:3]
            delta_rot = Rotation.from_rotvec(action[3:])
            target[:3, :3] = delta_rot.as_matrix() @ target[:3, :3]
            return target

    def _send_target(self, target) -> None:
        """Send target to robot via RobotClient."""
        if self.action_mode.startswith("joint"):
            self._robot_call(
                lambda: self._robot.set("q_desired", target), "set q_desired"
            )
        else:
            self._robot_call(
                lambda: self._robot.set("ee_desired", target), "set ee_desired"
            )

    # ── Safety ───────────────────────────────────────────────────

    def _clip_safety(self, target):
        """Clip target to safe limits.

        Joint modes: clip to joint limits.
        EE modes: no clip (OSC handles safety internally).
        """
        if self.action_mode.startswith("joint"):
            return np.clip(target, JOINT_LIMIT_LOW, JOINT_LIMIT_HIGH)
        return target

    # ── Gripper ──────────────────────────────────────────────────

    def _handle_gripper(self, action: float) -> None:
        """Process gripper action based on gripper_mode.

        continuous: action is target width [m], non-blocking move.
        binary: action is [0, 1], threshold at 0.5, with debounce.
        """
        if self._gripper is None:
            return

        if self.gripper_mode == "continuous":
            width = float(action)
            ok = self._gripper.move(width=width, speed=GRIPPER_SPEED)
            if not ok:
                logger.warning("Gripper move(%.4f) failed", width)

        elif self.gripper_mode == "binary":
            now = time.time()
            if now - self._last_gripper_time < GRIPPER_SLEEP:
                return

            command = "open" if action >= GRIPPER_THRESHOLD else "close"
            if command == self._last_gripper_command:
                return

            if command == "open":
                ok = self._gripper.open(width=self._gripper_max_width,
                                        speed=GRIPPER_SPEED)
            else:
                ok = self._gripper.grasp(
                    width=0.0, speed=GRIPPER_SPEED,
                    force=self._grasp_force
                )

            if ok:
                self._last_gripper_command = command
                self._last_gripper_time = now
            else:
                logger.warning("Gripper %s failed", command)

    # ── Internal helpers ─────────────────────────────────────────

    def _robot_call(self, method, label: str) -> None:
        """Call a RobotClient method, raise on failure.

        RobotClient returns bool (False = failure) instead of raising,
        unlike the local aiofranka controller. This helper restores
        the raise-on-failure behavior so callers see consistent errors.
        """
        ok = method()
        if not ok:
            raise RuntimeError(f"Robot command failed: {label}")

    def _update_current_state(self) -> None:
        """Cache current joint positions and EE pose from RobotClient."""
        if self._robot is None:
            return
        state = self._robot.state
        self._current_qpos = state["qpos"].copy()
        self._current_ee = state["ee"].copy()
