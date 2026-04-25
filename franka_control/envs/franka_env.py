"""Franka Gym Environment.

Dual-machine architecture: algorithm machine (this code) communicates with
control machine via TCP. Robot control via RobotClient (ZMQ → RobotServer
→ aiofranka), gripper via GripperClient (ZMQ → GripperServer → pylibfranka).

Standard Gymnasium interface: reset() / step() / close().

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
EE_ABS_LOW = np.array([-0.8, -0.8, 0.0, -2 * np.pi, -2 * np.pi, -2 * np.pi])
EE_ABS_HIGH = np.array([0.8, 0.8, 1.2, 2 * np.pi, 2 * np.pi, 2 * np.pi])

# ee_delta bounds: position [m] + rotation [rad]
EE_DELTA_LIMIT = np.array([0.05, 0.05, 0.05, 0.3, 0.3, 0.3])

# Gripper defaults
GRIPPER_SPEED = 0.1       # fixed speed [m/s]
GRIPPER_FORCE = 40.0      # default grasp force [N]
GRIPPER_MAX_WIDTH = 0.08  # max width [m]
GRIPPER_THRESHOLD = 0.5   # binary mode threshold


_VALID_ACTION_MODES = {"joint_abs", "joint_delta", "ee_abs", "ee_delta"}


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

        if action_mode not in _VALID_ACTION_MODES:
            raise ValueError(
                f"action_mode must be one of {_VALID_ACTION_MODES}, "
                f"got '{action_mode}'"
            )
        self.action_mode = action_mode
        self.use_gripper = gripper_host is not None
        self.gripper_mode = gripper_mode
        self._grasp_force = grasp_force
        self.home_qpos = (
            home_qpos if home_qpos is not None else DEFAULT_HOME_QPOS.copy()
        )

        # Action / observation dimensions
        self._robot_action_dim = 7 if action_mode.startswith("joint") else 6
        self._build_action_space()

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

        # Robot connection
        self.robot_ip = robot_ip
        self._robot_port = robot_port
        self._robot: Optional[RobotClient] = None

        # Gripper connection
        self._gripper: Optional[GripperClient] = None
        self._gripper_host = gripper_host
        self._gripper_port = gripper_port
        self._last_gripper_command: Optional[str] = None
        self._gripper_max_width = GRIPPER_MAX_WIDTH
        self._cached_gripper_width = 0.0

        # State cache — only updated via _refresh_state()
        self._current_qpos = np.zeros(7, dtype=np.float64)
        self._current_qvel = np.zeros(7, dtype=np.float64)
        self._current_ee = np.eye(4, dtype=np.float64)
        self._current_jac = np.zeros((6, 7), dtype=np.float64)
        self._current_torque = np.zeros(7, dtype=np.float64)

        # Delta mode targets — updated by _compute_robot_target(),
        # synced to actual state after reset/move_to/set_action_mode
        self._desired_qpos = np.zeros(7, dtype=np.float64)
        self._desired_ee = np.eye(4, dtype=np.float64)

    # ── Properties ──────────────────────────────────────────────

    @property
    def _ctrl_type(self) -> str:
        """Controller type for current action_mode."""
        return "pid" if self.action_mode.startswith("joint") else "osc"

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
        if not self._robot.connect(controller_type=self._ctrl_type):
            raise RuntimeError("Failed to connect to robot")
        logger.info("Robot connected. Mode: %s", self.action_mode)

        if self.use_gripper:
            logger.info("Connecting to gripper at %s:%d ...",
                        self._gripper_host, self._gripper_port)
            self._gripper = GripperClient(
                self._gripper_host, self._gripper_port
            )
            self._gripper.homing()
            state = self._gripper.get_state()
            if state:
                self._gripper_max_width = state.get(
                    "max_width", GRIPPER_MAX_WIDTH
                )
                self._cached_gripper_width = state.get("width", 0.0)
            logger.info("Gripper connected. Max width: %.4f m",
                        self._gripper_max_width)

        self._refresh_state()
        self._sync_desired_state()

    def _ensure_connected(self) -> None:
        """Connect if not already connected."""
        if self._robot is None:
            self.connect()

    # ── Gym interface ────────────────────────────────────────────

    def reset(self, *, seed=None, options=None):
        """Reset environment: move to home, open gripper.

        Returns:
            (observation, info)
        """
        super().reset(seed=seed)
        self._ensure_connected()
        self.move_to(self.home_qpos)
        if self.use_gripper:
            self._reset_gripper()
        return self._build_observation(), {}

    def step(self, action: np.ndarray):
        """Execute one step.

        Args:
            action: Physical-unit action array.
                Robot part: see action_space bounds (rad, m, etc.)
                Gripper part: [0, max_width] or [0, 1] depending on mode

        Returns:
            (observation, reward, terminated, truncated, info)
            info contains "applied_action": the action after clipping.
        """
        action = np.asarray(action, dtype=np.float32)
        applied_action = np.clip(
            action, self.action_space.low, self.action_space.high
        ).copy()

        robot_action, gripper_action = self._split_action(applied_action)
        target = self._compute_robot_target(robot_action)
        target = self._clip_robot_target(target)
        self._send_robot_target(target)

        if gripper_action is not None:
            self._apply_gripper_action(gripper_action)

        self._refresh_state()
        return self._build_observation(), 0.0, False, False, {
            "applied_action": applied_action,
        }

    def get_observation(self) -> dict:
        """Read current observation (refreshes state from robot)."""
        if self._robot is None:
            raise RuntimeError(
                "Not connected. Call connect() or reset() first."
            )
        self._refresh_state()
        return self._build_observation()

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

        Switches to PID mode (move updates q_desired, which PID tracks),
        executes move, then restores the original controller type.
        No stop/start needed — aiofranka's move() works while the
        control loop is running.

        Args:
            qpos: Target joint angles [rad], shape (7,).
        """
        if self._robot is None:
            raise RuntimeError(
                "Not connected. Call connect() or reset() first."
            )
        target = np.clip(qpos, JOINT_LIMIT_LOW, JOINT_LIMIT_HIGH)
        self._robot_call(
            lambda: self._robot.switch("pid"), "switch pid"
        )
        self._robot_call(lambda: self._robot.move(target), "move")
        self._robot_call(
            lambda: self._robot.switch(self._ctrl_type),
            f"switch {self._ctrl_type}",
        )
        self._refresh_state()
        self._sync_desired_state()

    def set_action_mode(self, mode: str) -> None:
        """Switch control mode at runtime.

        Switches the remote controller first. Only updates local state
        (action_mode, action_space) after the remote switch succeeds.

        Args:
            mode: One of joint_abs, joint_delta, ee_abs, ee_delta.
        """
        if mode not in _VALID_ACTION_MODES:
            raise ValueError(
                f"action_mode must be one of {_VALID_ACTION_MODES}, "
                f"got '{mode}'"
            )
        if self._robot is None:
            raise RuntimeError(
                "Not connected. Call connect() or reset() first."
            )

        # Remote first — if this fails, local state is untouched
        ctrl_type = "pid" if mode.startswith("joint") else "osc"
        self._robot_call(
            lambda: self._robot.switch(ctrl_type), f"switch {ctrl_type}"
        )

        # Remote succeeded — update local state
        self.action_mode = mode
        self._robot_action_dim = 7 if mode.startswith("joint") else 6
        self._build_action_space()
        self._sync_desired_state()
        logger.info("Action mode switched to: %s", mode)

    # ── Action computation (pure logic, no communication) ────────

    def _split_action(self, action: np.ndarray):
        """Split action into robot and gripper parts."""
        robot_action = action[: self._robot_action_dim]
        gripper_action = (
            action[self._robot_action_dim] if self.use_gripper else None
        )
        return robot_action, gripper_action

    def _compute_robot_target(self, action: np.ndarray):
        """Convert physical-unit action to controller target.

        Returns:
            np.ndarray [7] for joint modes (joint angles),
            np.ndarray [4x4] for ee modes (homogeneous matrix).
        """
        if self.action_mode == "joint_abs":
            return action.astype(np.float64)

        elif self.action_mode == "joint_delta":
            self._desired_qpos = self._desired_qpos + action
            return self._desired_qpos.copy()

        elif self.action_mode == "ee_abs":
            target = np.eye(4)
            target[:3, 3] = action[:3]
            target[:3, :3] = Rotation.from_rotvec(action[3:]).as_matrix()
            return target

        elif self.action_mode == "ee_delta":
            self._desired_ee[:3, 3] += action[:3]
            delta_rot = Rotation.from_rotvec(action[3:])
            self._desired_ee[:3, :3] = delta_rot.as_matrix() @ self._desired_ee[:3, :3]
            return self._desired_ee.copy()

    def _clip_robot_target(self, target):
        """Clip target to safe limits.

        Joint modes: clip to joint limits.
        EE modes: no clip (OSC handles safety internally).
        """
        if self.action_mode.startswith("joint"):
            return np.clip(target, JOINT_LIMIT_LOW, JOINT_LIMIT_HIGH)
        return target

    def _send_robot_target(self, target) -> None:
        """Send target to robot via RobotClient."""
        if self.action_mode.startswith("joint"):
            self._robot_call(
                lambda: self._robot.set("q_desired", target), "set q_desired"
            )
        else:
            self._robot_call(
                lambda: self._robot.set("ee_desired", target), "set ee_desired"
            )

    # ── Gripper ──────────────────────────────────────────────────

    def _apply_gripper_action(self, action: float) -> None:
        """Execute gripper action.

        continuous: send target width every step (width can change).
        binary: edge-triggered — only send on open↔close transitions.
        """
        if self._gripper is None:
            return

        if self.gripper_mode == "continuous":
            width = float(action)
            ok = self._gripper.move(width=width, speed=GRIPPER_SPEED)
            if not ok:
                logger.warning("Gripper move(%.4f) failed", width)
            else:
                self._cached_gripper_width = width

        elif self.gripper_mode == "binary":
            command = "open" if action >= GRIPPER_THRESHOLD else "close"
            if command == self._last_gripper_command:
                return

            if command == "open":
                ok = self._gripper.open(
                    width=self._gripper_max_width, speed=GRIPPER_SPEED
                )
            else:
                ok = self._gripper.grasp(
                    width=0.0, speed=GRIPPER_SPEED, force=self._grasp_force
                )

            # Update state regardless — grasp() returns False when the object
            # prevents fingers from reaching target width, but the gripper is
            # still holding the object. Not updating _last_gripper_command
            # would cause repeated grasp() calls every step.
            self._last_gripper_command = command
            if ok:
                self._cached_gripper_width = (
                    self._gripper_max_width if command == "open" else 0.0
                )
            else:
                logger.warning("Gripper %s failed", command)

    def _reset_gripper(self) -> None:
        """Open gripper for reset. Failure is non-fatal (warning only)."""
        if self._gripper is None:
            return
        ok = self._gripper.open(
            width=self._gripper_max_width, speed=GRIPPER_SPEED
        )
        if ok:
            self._last_gripper_command = "open"
            self._cached_gripper_width = self._gripper_max_width
        else:
            logger.warning("Gripper reset (open) failed")

    # ── State and observation ────────────────────────────────────

    def _refresh_state(self) -> None:
        """Read robot state and update cache. No gripper read."""
        if self._robot is None:
            return
        state = self._robot.state
        self._current_qpos = state["qpos"].copy()
        self._current_qvel = state["qvel"].copy()
        self._current_ee = state["ee"].copy()
        self._current_jac = state["jac"].copy()
        self._current_torque = state["last_torque"].copy()

    def _sync_desired_state(self) -> None:
        """Sync delta mode targets to current actual state.

        Must be called after any operation that moves the robot outside
        of step() — reset, move_to, set_action_mode, connect.
        """
        self._desired_qpos = self._current_qpos.copy()
        self._desired_ee = self._current_ee.copy()

    def _build_observation(self) -> dict:
        """Construct observation dict from cached state.

        Robot state comes from cache (updated by _refresh_state).
        Gripper width is read live from GripperClient.
        Does NOT do robot communication.
        """
        obs = {
            "joint_pos": self._current_qpos.astype(np.float32),
            "joint_vel": self._current_qvel.astype(np.float32),
            "joint_torque": self._current_torque.astype(np.float32),
            "ee_pos": self._current_ee[:3, 3].astype(np.float32),
            "ee_quat": Rotation.from_matrix(self._current_ee[:3, :3])
            .as_quat()
            .astype(np.float32),
            "ee_vel": (self._current_jac @ self._current_qvel).astype(
                np.float32
            ),
        }

        if self.use_gripper:
            obs["gripper_width"] = np.array(
                [self._cached_gripper_width], dtype=np.float32
            )

        return obs

    # ── Action space construction ────────────────────────────────

    def _build_action_space(self) -> None:
        """Build action_space from current action_mode and gripper_mode."""
        robot_low, robot_high = self._get_robot_action_bounds()
        gripper_low, gripper_high = self._get_gripper_action_bounds()
        self.action_space = gym.spaces.Box(
            low=np.concatenate([robot_low, gripper_low]),
            high=np.concatenate([robot_high, gripper_high]),
            dtype=np.float32,
        )

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

    # ── Internal helpers ─────────────────────────────────────────

    def _robot_call(self, method, label: str) -> None:
        """Call a RobotClient method, raise on failure.

        RobotClient returns bool (False = failure) instead of raising.
        This helper restores raise-on-failure so callers see consistent errors.
        """
        ok = method()
        if not ok:
            raise RuntimeError(f"Robot command failed: {label}")
