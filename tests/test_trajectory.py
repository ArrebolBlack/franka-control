"""Tests for trajectory route helpers that do not require robot hardware."""

import numpy as np

from franka_control.trajectory.executor import route_to_waypoints, split_route
from franka_control.trajectory.waypoints import GripperAction, WaypointStore


def _make_store() -> WaypointStore:
    store = WaypointStore()
    store.add_waypoint("home", np.zeros(7))
    store.add_waypoint("grasp", np.ones(7))
    store.add_waypoint("lift", np.full(7, 2.0))
    return store


def test_route_to_waypoints_preserves_route_order():
    store = _make_store()
    store.add_route("pick", ["home", "grasp", "lift"])

    waypoints = route_to_waypoints(store, "pick")

    assert waypoints.shape == (3, 7)
    assert np.allclose(waypoints[0], np.zeros(7))
    assert np.allclose(waypoints[1], np.ones(7))
    assert np.allclose(waypoints[2], np.full(7, 2.0))


def test_split_route_handles_pre_and_index_gripper_actions():
    store = _make_store()
    store.add_route(
        "pick",
        ["home", "grasp", "lift", "home"],
        gripper_actions={
            0: GripperAction("open"),
            "grasp": GripperAction("close"),
            3: GripperAction("open"),
        },
    )

    result = split_route(store, "pick")

    assert result.pre_gripper_action is not None
    assert result.pre_gripper_action.action == "open"
    assert len(result.segments) == 2
    assert result.segments[0].waypoints.shape == (2, 7)
    assert result.segments[0].gripper_action.action == "close"
    assert result.segments[1].waypoints.shape == (3, 7)
    assert result.segments[1].gripper_action.action == "open"
