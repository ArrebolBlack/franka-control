"""SpaceMouse Teleop — action provider for FrankaEnv.

Supports two modes:
  - get_action(): pure teleop, action entirely from SpaceMouse
  - maybe_override(action): intervention mode, overrides given action
    when SpaceMouse is active (for HG-DAgger style training)

Architecture:
  - Separate process polls SpaceMouse at max speed
  - Shared state via multiprocessing.Manager dict
  - Main thread reads latest state non-blocking

Usage:
    teleop = SpaceMouseTeleop(action_scale=(0.04, 0.2))

    # Pure teleop
    action, info = teleop.get_action()
    obs, _, _, _, _ = env.step(action)

    # Intervention
    action = policy(obs)
    action, info = teleop.maybe_override(action)
"""

from __future__ import annotations

import logging
import multiprocessing
from typing import Optional

import numpy as np

try:
    import pyspacemouse
except ImportError:
    pyspacemouse = None

logger = logging.getLogger(__name__)

# Default action scale: (translation [m], rotation [rad])
DEFAULT_ACTION_SCALE = (0.04, 0.2)

# Default deadzone: ignore input with norm below this
DEFAULT_DEADZONE = 0.001

# Default axis remapping: SpaceMouse raw → robot base frame
# Format: (source_axis, sign_flip)
# SpaceMouse raw: [x, y, z, pitch, roll, yaw]
# Robot base: depends on SpaceMouse orientation on desk
# Default assumes facing x-axis (same as serl): [-y, x, z, -roll, -pitch, -yaw]
DEFAULT_AXIS_REMAP = [
    ("y", -1),      # robot x = -mouse_y
    ("x", 1),       # robot y = +mouse_x
    ("z", 1),       # robot z = +mouse_z
    ("roll", -1),   # robot rx = -mouse_roll
    ("pitch", -1),  # robot ry = -mouse_pitch
    ("yaw", 1),     # robot rz = +mouse_yaw
]


class SpaceMouseTeleop:
    """SpaceMouse teleoperation action provider.

    Spawns a background process to continuously poll the SpaceMouse.
    The main thread reads the latest state non-blocking via get_action().

    Args:
        action_scale: (translation_scale [m], rotation_scale [rad]).
            SpaceMouse output [-1,1] is multiplied by these to get
            physical-unit deltas.
        deadzone: Input with L2 norm below this is treated as zero.
        axis_remap: List of (source_axis, sign) tuples defining the
            coordinate frame mapping from SpaceMouse to robot base.
        gripper_mode: "binary" (left=close, right=open) or None
            (no gripper control from SpaceMouse).
    """

    def __init__(
        self,
        action_scale: tuple[float, float] = DEFAULT_ACTION_SCALE,
        deadzone: float = DEFAULT_DEADZONE,
        axis_remap: Optional[list[tuple[str, int]]] = None,
        gripper_mode: Optional[str] = "binary",
    ):
        if pyspacemouse is None:
            raise ImportError(
                "pyspacemouse is not installed. "
                "Install with: pip install pyspacemouse"
            )

        self._action_scale = action_scale
        self._deadzone = deadzone
        self._axis_remap = axis_remap or DEFAULT_AXIS_REMAP
        self._gripper_mode = gripper_mode
        self._last_gripper = 1.0  # default open

        # Shared state with polling process
        self._manager = multiprocessing.Manager()
        self._shared = self._manager.dict()
        self._shared["raw"] = [0.0] * 6
        self._shared["buttons"] = [0] * 2
        self._shared["alive"] = True

        # Start polling process
        self._process = multiprocessing.Process(
            target=self._poll_loop, daemon=True
        )
        self._process.start()
        logger.info("SpaceMouseTeleop started (pid=%d)", self._process.pid)

    # ── Background polling ────────────────────────────────────────

    def _poll_loop(self) -> None:
        """Continuously poll SpaceMouse in background process."""
        try:
            device = pyspacemouse.open(nonblocking=True)
        except Exception as e:
            logger.error("Failed to open SpaceMouse: %s", e)
            return

        if device is None:
            logger.error("No SpaceMouse device found")
            return

        try:
            while self._shared.get("alive", False):
                state = device.read()
                if state is None:
                    continue
                self._shared["raw"] = [
                    state.x, state.y, state.z,
                    state.pitch, state.roll, state.yaw,
                ]
                btns = state.buttons
                if hasattr(btns, "__iter__"):
                    self._shared["buttons"] = [int(b) for b in btns]
                else:
                    self._shared["buttons"] = [0, 0]
        finally:
            device.close()

    # ── Public API ────────────────────────────────────────────────

    def get_action(self) -> tuple[np.ndarray, dict]:
        """Get current teleop action (physical units).

        Returns:
            action: [dx, dy, dz, drx, dry, drz] or
                    [dx, dy, dz, drx, dry, drz, gripper] if gripper_mode set.
            info: dict with keys:
                - "intervened": bool — whether SpaceMouse is active
                - "buttons": [left, right]
                - "raw": raw [-1,1] 6D output
        """
        raw = list(self._shared.get("raw", [0.0] * 6))
        buttons = list(self._shared.get("buttons", [0, 0]))

        # Apply axis remapping
        axis_map = {
            "x": raw[0], "y": raw[1], "z": raw[2],
            "pitch": raw[3], "roll": raw[4], "yaw": raw[5],
        }
        remapped = np.array([
            axis_map[name] * sign for name, sign in self._axis_remap
        ], dtype=np.float64)

        # Split translation and rotation
        translation = remapped[:3]
        rotation = remapped[3:]

        # Deadzone check
        intervened = bool(np.linalg.norm(remapped) > self._deadzone)

        # Scale to physical units
        translation *= self._action_scale[0]
        rotation *= self._action_scale[1]

        robot_action = np.concatenate([translation, rotation])

        # Gripper
        if self._gripper_mode == "binary":
            left, right = buttons[0], buttons[1]
            if left:
                self._last_gripper = 0.0  # close
                intervened = True
            elif right:
                self._last_gripper = 1.0  # open
                intervened = True
            gripper = self._last_gripper
            action = np.append(robot_action, gripper)
        else:
            action = robot_action
            gripper = None

        info = {
            "intervened": intervened,
            "buttons": buttons,
            "raw": raw,
            "gripper": gripper,
        }
        return action, info

    def maybe_override(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, dict]:
        """Override given action if SpaceMouse is active (intervention).

        Used for HG-DAgger style training: policy proposes action,
        human can override via SpaceMouse at any time.

        Args:
            action: Policy-proposed action (physical units).

        Returns:
            action: Either teleop action (if intervened) or original.
            info: dict with "intervened" and other metadata.
        """
        teleop_action, info = self.get_action()

        if info["intervened"]:
            return teleop_action, info
        info["intervened"] = False
        return action.copy(), info

    # ── Cleanup ───────────────────────────────────────────────────

    def close(self) -> None:
        """Stop polling process and release SpaceMouse."""
        self._shared["alive"] = False
        if self._process.is_alive():
            self._process.join(timeout=2.0)
            if self._process.is_alive():
                self._process.terminate()
        self._manager.shutdown()
        logger.info("SpaceMouseTeleop stopped.")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @property
    def action_dim(self) -> int:
        """Return expected action dimension (6 + optional gripper)."""
        return 7 if self._gripper_mode else 6
