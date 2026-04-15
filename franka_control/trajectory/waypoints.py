"""Waypoint and route management for trajectory planning.

Stores named waypoints (joint angles) and routes (ordered waypoint lists
with optional gripper actions) in a single YAML file.

Usage:
    store = WaypointStore()
    store.add_waypoint("home", joint_angles=np.array([...]))
    store.add_route("pick_place", ["home", "above", "grasp", "home"],
                    gripper_actions={"grasp": GripperAction("close")})
    store.save("config/waypoints.yaml")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import yaml

logger = logging.getLogger(__name__)


@dataclass
class Waypoint:
    """Named joint configuration."""

    name: str
    joint_angles: np.ndarray  # (7,) rad
    label: str = ""


@dataclass
class GripperAction:
    """Gripper action at a waypoint."""

    action: str  # "open" or "close"


@dataclass
class Route:
    """Named route through ordered waypoints with optional gripper actions."""

    name: str
    waypoints: list[str]  # ordered waypoint names
    gripper_actions: dict[str, GripperAction] = field(default_factory=dict)
    label: str = ""


class WaypointStore:
    """Manage waypoints and routes in a single YAML file.

    YAML format::

        waypoints:
          home:
            joint_angles: [0.0, -0.785, ...]
            label: "安全起始位"
        routes:
          pick_place:
            waypoints: [home, above, grasp, home]
            gripper_actions:
              grasp: close
            label: "抓取放置"
    """

    def __init__(self):
        self._waypoints: dict[str, Waypoint] = {}
        self._routes: dict[str, Route] = {}

    # ── Persistence ──────────────────────────────────────────────

    def load(self, path: str) -> None:
        """Load from YAML file (replaces all in-memory data)."""
        with open(path, "r") as f:
            data = yaml.safe_load(f) or {}

        self._waypoints.clear()
        self._routes.clear()

        for name, entry in (data.get("waypoints") or {}).items():
            self._waypoints[name] = Waypoint(
                name=name,
                joint_angles=np.array(entry["joint_angles"], dtype=np.float64),
                label=entry.get("label", ""),
            )

        for name, entry in (data.get("routes") or {}).items():
            wp_names = entry.get("waypoints") or []
            gripper_actions = {}
            for wp_name, ga in (entry.get("gripper_actions") or {}).items():
                action_str = ga if isinstance(ga, str) else ga.get("action", "close")
                gripper_actions[wp_name] = GripperAction(action=action_str)
            self._routes[name] = Route(
                name=name,
                waypoints=wp_names,
                gripper_actions=gripper_actions,
                label=entry.get("label", ""),
            )

        logger.info(
            "Loaded %d waypoints, %d routes from %s",
            len(self._waypoints), len(self._routes), path,
        )

    def save(self, path: str) -> None:
        """Save to YAML file."""
        data: dict = {"waypoints": {}, "routes": {}}

        for name, wp in self._waypoints.items():
            data["waypoints"][name] = {
                "joint_angles": wp.joint_angles.tolist(),
                "label": wp.label,
            }

        for name, route in self._routes.items():
            route_data: dict = {
                "waypoints": route.waypoints,
                "label": route.label,
            }
            if route.gripper_actions:
                route_data["gripper_actions"] = {
                    wp_name: ga.action
                    for wp_name, ga in route.gripper_actions.items()
                }
            data["routes"][name] = route_data

        with open(path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        logger.info("Saved %d waypoints, %d routes to %s",
                    len(self._waypoints), len(self._routes), path)

    # ── Waypoint CRUD ────────────────────────────────────────────

    def add_waypoint(
        self, name: str, joint_angles: np.ndarray, label: str = ""
    ) -> None:
        self._waypoints[name] = Waypoint(
            name=name,
            joint_angles=np.asarray(joint_angles, dtype=np.float64),
            label=label,
        )

    def get_waypoint(self, name: str) -> Waypoint:
        return self._waypoints[name]

    def remove_waypoint(self, name: str) -> bool:
        if name in self._waypoints:
            del self._waypoints[name]
            return True
        return False

    def has_waypoint(self, name: str) -> bool:
        return name in self._waypoints

    def list_waypoint_names(self) -> list[str]:
        return list(self._waypoints.keys())

    # ── Route CRUD ───────────────────────────────────────────────

    def add_route(
        self,
        name: str,
        waypoint_names: list[str],
        gripper_actions: Optional[dict[str, GripperAction]] = None,
        label: str = "",
    ) -> None:
        self._routes[name] = Route(
            name=name,
            waypoints=list(waypoint_names),
            gripper_actions=gripper_actions or {},
            label=label,
        )

    def get_route(self, name: str) -> Route:
        return self._routes[name]

    def remove_route(self, name: str) -> bool:
        if name in self._routes:
            del self._routes[name]
            return True
        return False

    def has_route(self, name: str) -> bool:
        return name in self._routes

    def list_route_names(self) -> list[str]:
        return list(self._routes.keys())
