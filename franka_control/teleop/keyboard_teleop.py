"""Keyboard teleoperation provider for FrankaEnv.

Uses pynput to capture real keydown/keyup events and converts the current
pressed-key set into normalized Cartesian velocity commands in [-1, 1].
The teleop script multiplies the first 6 dimensions by dt to produce ee_delta.
"""

from __future__ import annotations

import logging
import threading
from typing import Optional

import numpy as np

try:
    from pynput import keyboard
except ImportError:
    keyboard = None

logger = logging.getLogger(__name__)

DEFAULT_ACTION_SCALE = (2.0, 5.0)
SLOW_MODE_SCALE = 0.25

_CHAR_KEY_TO_AXIS = {
    "w": (0, 1.0),
    "s": (0, -1.0),
    "a": (1, 1.0),
    "d": (1, -1.0),
    "r": (2, 1.0),
    "f": (2, -1.0),
    "q": (5, 1.0),
    "e": (5, -1.0),
    "z": (4, 1.0),
    "x": (4, -1.0),
    "c": (3, 1.0),
    "v": (3, -1.0),
}


class KeyboardTeleop:
    """Keyboard teleoperation action provider.

    Args:
        action_scale: Max translation/rotation speed used by the caller.
        freeze_rotation: If True, zero out the rotation component.
        gripper_mode: "binary" or None.
    """

    def __init__(
        self,
        action_scale: tuple[float, float] = DEFAULT_ACTION_SCALE,
        freeze_rotation: bool = False,
        gripper_mode: Optional[str] = "binary",
    ):
        if keyboard is None:
            raise ImportError(
                "pynput is not installed. Install with: pip install pynput"
            )

        self._action_scale = action_scale
        self._freeze_rotation = freeze_rotation
        self._gripper_mode = gripper_mode
        self._lock = threading.Lock()
        self._pressed_keys: set[object] = set()
        self._last_gripper = 1.0
        self._close_pressed = False
        self._open_pressed = False
        self._exit_requested = False

        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()
        logger.info("KeyboardTeleop started")

    def _normalize_key(self, key) -> object:
        """Normalize pynput keys so chars compare case-insensitively."""
        key_char = getattr(key, "char", None)
        if key_char:
            return key_char.lower()
        return key

    def _on_press(self, key) -> None:
        normalized = self._normalize_key(key)
        with self._lock:
            self._pressed_keys.add(normalized)
            if normalized == keyboard.Key.esc:
                self._exit_requested = True

    def _on_release(self, key) -> None:
        normalized = self._normalize_key(key)
        with self._lock:
            self._pressed_keys.discard(normalized)

    def get_action(self) -> tuple[np.ndarray, dict]:
        """Get the current normalized velocity command."""
        with self._lock:
            pressed_keys = set(self._pressed_keys)
            exit_requested = self._exit_requested
            self._exit_requested = False  # consume on read

        action = np.zeros(6, dtype=np.float64)
        for key_char, (axis, direction) in _CHAR_KEY_TO_AXIS.items():
            if key_char in pressed_keys:
                action[axis] += direction
        action = np.clip(action, -1.0, 1.0)

        if self._freeze_rotation:
            action[3:] = 0.0

        slow_mode = (
            keyboard.Key.shift in pressed_keys
            or keyboard.Key.shift_l in pressed_keys
            or keyboard.Key.shift_r in pressed_keys
        )
        if slow_mode:
            action *= SLOW_MODE_SCALE

        action[:3] *= self._action_scale[0]
        action[3:] *= self._action_scale[1]

        gripper = None
        gripper_intervened = False
        if self._gripper_mode == "binary":
            close_now = keyboard.Key.space in pressed_keys
            open_now = keyboard.Key.enter in pressed_keys

            if close_now and not self._close_pressed:
                self._last_gripper = 0.0
                gripper_intervened = True
            elif open_now and not self._open_pressed:
                self._last_gripper = 1.0
                gripper_intervened = True

            self._close_pressed = close_now
            self._open_pressed = open_now
            gripper = self._last_gripper
            action = np.append(action, gripper)

        info = {
            "intervened": bool(np.any(action[:6] != 0.0)) or gripper_intervened,
            "pressed_keys": sorted(str(k) for k in pressed_keys),
            "gripper": gripper,
            "exit_requested": exit_requested,
            "slow_mode": slow_mode,
        }
        return action, info

    def maybe_override(
        self, action: np.ndarray
    ) -> tuple[np.ndarray, dict]:
        """Override a proposed action when keyboard input is active."""
        teleop_action, info = self.get_action()
        if info["intervened"]:
            return teleop_action, info
        return action.copy(), info

    def set_freeze_rotation(self, freeze: bool) -> None:
        """Toggle rotation freezing at runtime."""
        self._freeze_rotation = freeze

    def clear_pressed_keys(self) -> None:
        """Clear pressed key state.

        Call after terminal mode switches (e.g. input()) to prevent
        stale key events from triggering unintended actions.
        Does NOT reset _last_gripper — gripper state is preserved.
        """
        with self._lock:
            self._pressed_keys.clear()
            self._close_pressed = False
            self._open_pressed = False

    def close(self) -> None:
        """Stop listening to keyboard events."""
        self._listener.stop()
        self._listener.join(timeout=2.0)
        logger.info("KeyboardTeleop stopped.")

    @property
    def action_dim(self) -> int:
        """Return expected action dimension (6 + optional gripper)."""
        return 7 if self._gripper_mode else 6
