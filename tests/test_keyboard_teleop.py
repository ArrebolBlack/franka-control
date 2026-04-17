"""Tests for KeyboardTeleop without requiring a real desktop keyboard hook."""

from __future__ import annotations

import os
import sys

import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from franka_control.teleop import keyboard_teleop as kt


class _FakeListener:
    def __init__(self, on_press, on_release):
        self.on_press = on_press
        self.on_release = on_release
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True

    def stop(self):
        self.stopped = True

    def join(self, timeout=None):
        return None


class _FakeKey:
    space = "space"
    enter = "enter"
    esc = "esc"
    shift = "shift"
    shift_l = "shift_l"
    shift_r = "shift_r"


class _FakeKeyboard:
    Key = _FakeKey
    Listener = _FakeListener


class _FakeCharKey:
    def __init__(self, char: str):
        self.char = char


@pytest.fixture(autouse=True)
def _patch_keyboard(monkeypatch):
    monkeypatch.setattr(kt, "keyboard", _FakeKeyboard)


def _make_teleop(**kwargs):
    teleop = kt.KeyboardTeleop(**kwargs)
    assert teleop._listener.started is True
    return teleop


def test_translation_mapping_and_release():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode=None)
    try:
        teleop._on_press(_FakeCharKey("w"))
        action, info = teleop.get_action()
        assert np.allclose(action, np.array([2.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
        assert info["intervened"] is True

        teleop._on_release(_FakeCharKey("w"))
        action, info = teleop.get_action()
        assert np.allclose(action, np.zeros(6))
        assert info["intervened"] is False
    finally:
        teleop.close()


def test_rotation_mapping():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode=None)
    try:
        teleop._on_press(_FakeCharKey("q"))
        teleop._on_press(_FakeCharKey("z"))
        teleop._on_press(_FakeCharKey("c"))
        action, info = teleop.get_action()
        assert np.allclose(action, np.array([0.0, 0.0, 0.0, 5.0, 5.0, 5.0]))
        assert info["intervened"] is True
    finally:
        teleop.close()


def test_opposite_keys_cancel():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode=None)
    try:
        teleop._on_press(_FakeCharKey("w"))
        teleop._on_press(_FakeCharKey("s"))
        teleop._on_press(_FakeCharKey("a"))
        teleop._on_press(_FakeCharKey("d"))
        action, info = teleop.get_action()
        assert np.allclose(action, np.zeros(6))
        assert info["intervened"] is False
    finally:
        teleop.close()


def test_freeze_rotation_zeros_rotation_axes():
    teleop = _make_teleop(
        action_scale=(2.0, 5.0),
        freeze_rotation=True,
        gripper_mode=None,
    )
    try:
        teleop._on_press(_FakeCharKey("q"))
        teleop._on_press(_FakeCharKey("z"))
        teleop._on_press(_FakeCharKey("c"))
        action, _ = teleop.get_action()
        assert np.allclose(action, np.zeros(6))
    finally:
        teleop.close()


def test_shift_slow_mode_scales_action():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode=None)
    try:
        teleop._on_press(_FakeCharKey("w"))
        teleop._on_press(_FakeKeyboard.Key.shift)
        action, info = teleop.get_action()
        assert np.allclose(action, np.array([0.5, 0.0, 0.0, 0.0, 0.0, 0.0]))
        assert info["slow_mode"] is True
    finally:
        teleop.close()


def test_gripper_binary_is_edge_triggered():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode="binary")
    try:
        action, info = teleop.get_action()
        assert action.shape == (7,)
        assert action[-1] == 1.0
        assert info["intervened"] is False

        teleop._on_press(_FakeKeyboard.Key.space)
        action, info = teleop.get_action()
        assert action[-1] == 0.0
        assert info["intervened"] is True

        action, info = teleop.get_action()
        assert action[-1] == 0.0
        assert info["intervened"] is False

        teleop._on_release(_FakeKeyboard.Key.space)
        teleop._on_press(_FakeKeyboard.Key.enter)
        action, info = teleop.get_action()
        assert action[-1] == 1.0
        assert info["intervened"] is True
    finally:
        teleop.close()


def test_escape_sets_exit_requested():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode=None)
    try:
        teleop._on_press(_FakeKeyboard.Key.esc)
        _, info = teleop.get_action()
        assert info["exit_requested"] is True
    finally:
        teleop.close()


def test_maybe_override_respects_intervened_state():
    teleop = _make_teleop(action_scale=(2.0, 5.0), gripper_mode=None)
    try:
        base = np.ones(6, dtype=np.float64)
        action, info = teleop.maybe_override(base)
        assert np.allclose(action, base)
        assert info["intervened"] is False

        teleop._on_press(_FakeCharKey("w"))
        action, info = teleop.maybe_override(base)
        assert np.allclose(action, np.array([2.0, 0.0, 0.0, 0.0, 0.0, 0.0]))
        assert info["intervened"] is True
    finally:
        teleop.close()
