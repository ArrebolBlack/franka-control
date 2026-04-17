"""Interactive waypoint collection tool.

Uses SpaceMouse or keyboard for teleoperation and keyboard commands
for recording/managing waypoints and routes.

Usage:
    python -m franka_control.scripts.collect_waypoints \\
        --robot-ip 172.16.0.2 \\
        --waypoints config/waypoints.yaml

    python -m franka_control.scripts.collect_waypoints \\
        --robot-ip 172.16.0.2 \\
        --device keyboard \\
        --waypoints config/waypoints.yaml

Controls (Spacemouse device):
    SpaceMouse: 6-DOF Cartesian delta control
    Left button: close gripper, Right button: open gripper

    Keyboard (raw terminal mode):
        r  — Record current pose as waypoint
        g  — Goto waypoint (move to recorded position)
        p  — Create route from waypoint names
        d  — Delete waypoint or route
        l  — List all waypoints and routes
        w  — Save to YAML file
        q  — Quit (auto-saves)

Controls (Keyboard device):
    WASDRF: translation, QEZXC: rotation
    Space: close gripper, Enter: open gripper
    Shift: slow mode (0.25x)
    Number keys for commands:
        1  — Record current pose as waypoint
        2  — Goto waypoint
        3  — Create route
        4  — Delete waypoint or route
        5  — List all
        6  — Save
        Esc — Quit (auto-saves)
"""

from __future__ import annotations

import argparse
import logging
import os
import select
import sys
import termios
import time
import tty

import numpy as np

from franka_control.envs.franka_env import FrankaEnv
from franka_control.teleop import KeyboardTeleop, SpaceMouseTeleop
from franka_control.trajectory.waypoints import GripperAction, WaypointStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


# ── Terminal helpers ────────────────────────────────────────────


def _set_raw(fd: int) -> list:
    """Switch terminal to raw mode (single keypress, no echo)."""
    old = termios.tcgetattr(fd)
    tty.setraw(fd)
    return old


def _set_normal(fd: int, old_settings: list) -> None:
    """Restore terminal to normal mode."""
    termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def _drain_stdin(fd: int) -> None:
    """Discard any buffered bytes on stdin (e.g. after terminal mode switch)."""
    while select.select([fd], [], [], 0.0)[0]:
        os.read(fd, 1)


def _read_key_raw(fd: int, timeout: float = 0.01) -> str | None:
    """Read one keypress in raw mode with timeout. Returns None if no key."""
    dr, _, _ = select.select([fd], [], [], timeout)
    if dr:
        return os.read(fd, 1).decode("utf-8", errors="ignore")
    return None


def prompt_text(label: str) -> str:
    """Print label and read a line of text (normal terminal mode)."""
    return input(label).strip()


# ── Main ────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Interactive waypoint collection tool"
    )
    parser.add_argument("--robot-ip", required=True, help="Control machine IP")
    parser.add_argument("--gripper-host", default=None,
                        help="Gripper server host (default: same as --robot-ip)")
    parser.add_argument("--gripper-port", type=int, default=5556)
    parser.add_argument(
        "--waypoints", default="config/waypoints.yaml",
        help="YAML file path (default: config/waypoints.yaml)",
    )
    parser.add_argument(
        "--device",
        default="spacemouse",
        choices=["spacemouse", "keyboard"],
        help="Teleop device (default: spacemouse)",
    )
    parser.add_argument(
        "--action-scale-t", type=float, default=0.04,
        help="Translation scale [m] (default: 0.04)",
    )
    parser.add_argument(
        "--action-scale-r", type=float, default=0.2,
        help="Rotation scale [rad] (default: 0.2)",
    )
    parser.add_argument(
        "--hz", type=int, default=10, help="Control frequency [Hz] (default: 10)"
    )
    args = parser.parse_args()

    # Default gripper_host to robot_ip
    if args.gripper_host is None:
        args.gripper_host = args.robot_ip

    # Load or create waypoint store
    store = WaypointStore()
    if os.path.exists(args.waypoints):
        store.load(args.waypoints)
        logger.info(
            "Loaded %d waypoints, %d routes from %s",
            len(store.list_waypoint_names()),
            len(store.list_route_names()),
            args.waypoints,
        )

    # Create env + teleop
    use_gripper = args.gripper_host is not None
    env = FrankaEnv(
        robot_ip=args.robot_ip,
        gripper_host=args.gripper_host,
        gripper_port=args.gripper_port,
        action_mode="ee_delta",
        gripper_mode="binary" if use_gripper else "continuous",
    )

    use_keyboard = args.device == "keyboard"
    teleop_cls = KeyboardTeleop if use_keyboard else SpaceMouseTeleop
    teleop = teleop_cls(
        action_scale=(args.action_scale_t, args.action_scale_r),
        gripper_mode="binary" if use_gripper else None,
    )

    # Command key mappings: spacemouse uses letters, keyboard uses numbers
    # (to avoid conflict with WASDRF/QEZXC movement keys)
    if use_keyboard:
        CMD_KEYS = {
            "1": "record", "2": "goto", "3": "route",
            "4": "delete", "5": "list", "6": "save",
        }
        EXIT_KEYS = {"\x1b", "\x03"}  # Esc, Ctrl+C
    else:
        CMD_KEYS = {
            "r": "record", "g": "goto", "p": "route",
            "d": "delete", "l": "list", "w": "save",
        }
        EXIT_KEYS = {"q", "\x03"}  # q, Ctrl+C

    fd = sys.stdin.fileno()
    old_term = _set_raw(fd)

    def _restore_terminal():
        _set_normal(fd, old_term)

    try:
        logger.info("Connecting to robot...")
        obs, _ = env.reset()
        if use_keyboard:
            logger.info(
                "Ready. Movement: WASDRF=translate QEZXC=rotate Space=close Enter=open Shift=slow\n"
                "        Commands: 1=record 2=goto 3=route 4=delete 5=list 6=save Esc=quit"
            )
        else:
            logger.info(
                "Ready. SpaceMouse: left-btn=close right-btn=open\n"
                "        Commands: r=record g=goto p=route d=delete l=list w=save q=quit"
            )

        dt = 1.0 / args.hz

        while True:
            t_start = time.time()

            # Check keyboard commands
            key = _read_key_raw(fd, timeout=0.0)
            if key:
                if key in EXIT_KEYS:
                    break
                cmd = CMD_KEYS.get(key)
                if cmd:
                    if cmd == "record":
                        _handle_record(env, store, fd, old_term)
                    elif cmd == "goto":
                        _handle_goto(env, store, fd, old_term)
                    elif cmd == "route":
                        _handle_route(store, fd, old_term)
                    elif cmd == "delete":
                        _handle_delete(store, fd, old_term)
                    elif cmd == "list":
                        _handle_list(store, fd, old_term)
                    elif cmd == "save":
                        _handle_save(store, args.waypoints, fd, old_term)

                    # Clear stale pynput state after command handlers
                    # (input() Enter press not yet released physically)
                    if use_keyboard:
                        teleop.clear_pressed_keys()

            # Teleop step
            action, info = teleop.get_action()
            if use_keyboard:
                action[:6] *= dt
            if info.get("exit_requested"):
                break
            obs, _, _, _, _ = env.step(action)

            # Maintain frequency
            elapsed = time.time() - t_start
            if elapsed < dt:
                time.sleep(dt - elapsed)

    except Exception as e:
        logger.error("Error: %s", e)
    finally:
        _restore_terminal()
        os.makedirs(os.path.dirname(args.waypoints) or ".", exist_ok=True)
        store.save(args.waypoints)
        teleop.close()
        env.close()
        logger.info("Session ended.")


# ── Command handlers ────────────────────────────────────────────


def _switch_to_normal(fd, old_term):
    """Switch to normal terminal mode for text output/input."""
    _set_normal(fd, old_term)


def _switch_to_raw(fd, old_term):
    """Switch back to raw terminal and discard stale bytes."""
    _set_raw(fd)
    _drain_stdin(fd)


def _handle_record(env, store, fd, old_term):
    """Record current joint angles as a named waypoint."""
    _switch_to_normal(fd, old_term)
    try:
        print("\n--- Record Waypoint ---")
        name = prompt_text("  Name: ")
        if not name:
            print("  Cancelled.")
            return
        if store.has_waypoint(name):
            overwrite = prompt_text(f"  '{name}' exists. Overwrite? [y/N]: ")
            if overwrite.lower() != "y":
                print("  Cancelled.")
                return

        label = prompt_text("  Label (optional): ")
        qpos = env._current_qpos.copy()
        store.add_waypoint(name, qpos, label=label)
        print(f"  Recorded '{name}': {np.round(qpos, 3).tolist()}")
    finally:
        _switch_to_raw(fd, old_term)


def _handle_goto(env, store, fd, old_term):
    """Move to a recorded waypoint."""
    _switch_to_normal(fd, old_term)
    try:
        print("\n--- Goto Waypoint ---")
        name = prompt_text("  Waypoint name: ")
        if not name:
            print("  Cancelled.")
            return
        if not store.has_waypoint(name):
            print(f"  Waypoint '{name}' not found.")
            return

        wp = store.get_waypoint(name)
        print(f"  Moving to '{name}'...")
        env.move_to(wp.joint_angles)
        print(f"  Arrived at '{name}'.")
    finally:
        _switch_to_raw(fd, old_term)


def _handle_route(store, fd, old_term):
    """Create a route from waypoint names."""
    _switch_to_normal(fd, old_term)
    try:
        print("\n--- Create Route ---")
        route_name = prompt_text("  Route name: ")
        if not route_name:
            print("  Cancelled.")
            return

        print("  Enter waypoint names (one per line, empty line to finish):")
        wp_names = []
        while True:
            wp_name = prompt_text("    > ")
            if not wp_name:
                break
            if not store.has_waypoint(wp_name):
                print(f"    '{wp_name}' not found. Skip.")
                continue
            wp_names.append(wp_name)

        if len(wp_names) < 2:
            print("  Need at least 2 waypoints. Cancelled.")
            return

        # Ask for gripper actions
        print("  Enter gripper actions (name_or_index: open/close, empty to finish):")
        gripper_actions = {}
        while True:
            ga_input = prompt_text("    > ")
            if not ga_input:
                break
            if ":" not in ga_input:
                print("    Format: waypoint_name: open/close  or  index: open/close")
                continue
            key_str, action = ga_input.split(":", 1)
            key_str = key_str.strip()
            action = action.strip().lower()
            if action not in ("open", "close"):
                print(f"    Invalid action '{action}'. Use 'open' or 'close'.")
                continue
            # Accept integer index or waypoint name
            try:
                key: str | int = int(key_str)
                if key < 0 or key >= len(wp_names):
                    print(f"    Index {key} out of range (0-{len(wp_names)-1}). Skip.")
                    continue
            except ValueError:
                key = key_str
                if key not in wp_names:
                    print(f"    '{key}' not in route. Skip.")
                    continue
            gripper_actions[key] = GripperAction(action)

        label = prompt_text("  Label (optional): ")
        store.add_route(route_name, wp_names, gripper_actions or None, label=label)
        print(f"  Route '{route_name}' created: {wp_names}")
        if gripper_actions:
            print(f"  Gripper: {[(k, v.action) for k, v in gripper_actions.items()]}")
    finally:
        _switch_to_raw(fd, old_term)


def _handle_delete(store, fd, old_term):
    """Delete a waypoint or route."""
    _switch_to_normal(fd, old_term)
    try:
        print("\n--- Delete ---")
        print("  Prefix: wp=waypoint, rt=route")
        target = prompt_text("  Target (e.g. wp:home or rt:pick_place): ")
        if ":" not in target:
            print("  Invalid format. Use wp:name or rt:name.")
            return

        prefix, name = target.split(":", 1)
        if prefix == "wp":
            if store.remove_waypoint(name):
                print(f"  Waypoint '{name}' deleted.")
            else:
                print(f"  Waypoint '{name}' not found.")
        elif prefix == "rt":
            if store.remove_route(name):
                print(f"  Route '{name}' deleted.")
            else:
                print(f"  Route '{name}' not found.")
        else:
            print(f"  Unknown prefix '{prefix}'. Use 'wp' or 'rt'.")
    finally:
        _switch_to_raw(fd, old_term)


def _handle_list(store, fd, old_term):
    """Print all waypoints and routes."""
    _switch_to_normal(fd, old_term)
    try:
        print("\n--- Waypoints ---")
        for name in store.list_waypoint_names():
            wp = store.get_waypoint(name)
            label_str = f" ({wp.label})" if wp.label else ""
            print(f"  {name}{label_str}: {np.round(wp.joint_angles, 3).tolist()}")

        print("\n--- Routes ---")
        for name in store.list_route_names():
            route = store.get_route(name)
            label_str = f" ({route.label})" if route.label else ""
            ga_str = ""
            if route.gripper_actions:
                ga_str = " gripper=" + str(
                    {k: v.action for k, v in route.gripper_actions.items()}
                )
            print(f"  {name}{label_str}: {route.waypoints}{ga_str}")
    finally:
        _switch_to_raw(fd, old_term)


def _handle_save(store, path, fd, old_term):
    """Save waypoint store to YAML."""
    _switch_to_normal(fd, old_term)
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        store.save(path)
        print(f"  Saved to {path}")
    finally:
        _switch_to_raw(fd, old_term)


if __name__ == "__main__":
    main()
