"""Route splitting and trajectory execution for Franka robot.

Handles splitting routes at gripper action points into planning segments,
and executing planned trajectories on the robot via FrankaEnv.

Usage:
    from franka_control.trajectory.planner import TrajectoryPlanner
    from franka_control.trajectory.executor import execute_route
    execute_route(env, store, "pick_place", planner)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np

from franka_control.trajectory.planner import Trajectory, TrajectoryPlanner
from franka_control.trajectory.waypoints import GripperAction, WaypointStore

logger = logging.getLogger(__name__)


@dataclass
class RouteSegment:
    """One planning segment produced by split_route().

    A route is split at gripper action points. Each segment is planned
    independently with TOPPRA. Between segments, the gripper action
    is executed (blocking).

    Attributes:
        waypoints: (K, 7) joint angles for this segment.
        gripper_action: Gripper action at the END of this segment.
            Executed after the trajectory completes (blocking).
            None for the last segment (or segments without gripper).
    """

    waypoints: np.ndarray
    gripper_action: Optional[GripperAction]


@dataclass
class SplitResult:
    """Result of split_route().

    Supports iteration over segments for backward compatibility:
        result = split_route(store, "route")
        for seg in result:      # iterates over result.segments
            ...

    Attributes:
        segments: Planning segments to execute in order.
        pre_gripper_action: Gripper action to execute BEFORE the first
            segment (when the route's first waypoint has a gripper action).
            None if no pre-route action needed.
    """

    segments: list[RouteSegment]
    pre_gripper_action: Optional[GripperAction] = None

    def __iter__(self):
        return iter(self.segments)

    def __len__(self):
        return len(self.segments)


# ── Route helper functions ──────────────────────────────────────


def route_to_waypoints(
    store: WaypointStore, route_name: str
) -> np.ndarray:
    """Extract joint angles array from a route.

    Args:
        store: WaypointStore with loaded data.
        route_name: Name of the route.

    Returns:
        (N, 7) joint angles array.

    Raises:
        KeyError: If route or any referenced waypoint doesn't exist.
    """
    route = store.get_route(route_name)
    result = []
    for wp_name in route.waypoints:
        wp = store.get_waypoint(wp_name)
        result.append(wp.joint_angles)
    return np.array(result)


def split_route(
    store: WaypointStore, route_name: str
) -> SplitResult:
    """Split a route into planning segments at gripper action points.

    Each segment is planned independently with TOPPRA. Between segments,
    the robot stops at the endpoint and the gripper action is executed
    (blocking) via env.step().

    Gripper actions support two key formats in the route's gripper_actions
    dict:
      - Waypoint name (str): matches all occurrences of that waypoint.
      - Integer index: matches only the waypoint at that specific position.
    Index keys take priority over name keys when both match.

    Example:
        route = [home, above, grasp, lift, carry, release, home]
        gripper_actions = {grasp: close, release: open}

        -> Segment 1: [home, above, grasp],     gripper=close
        -> Segment 2: [grasp, lift, carry, release], gripper=open
        -> Segment 3: [release, home],           gripper=None

    With pre-route action and index-based matching:
        route = [home, grasp, lift, home]
        gripper_actions = {0: open, grasp: close, 3: open}

        -> pre_gripper_action: open  (index 0)
        -> Segment 1: [home, grasp, lift, home],  gripper=open (index 3)

    Args:
        store: WaypointStore with loaded data.
        route_name: Name of the route.

    Returns:
        SplitResult with segments and optional pre-route gripper action.
    """
    route = store.get_route(route_name)
    ga = route.gripper_actions  # keys: waypoint name (str) or index (int)

    # Build action_at_index: resolve gripper actions to route indices.
    # Integer keys take priority over name keys.
    action_at_index: dict[int, GripperAction] = {}
    for k, wp_name in enumerate(route.waypoints):
        # Integer index key takes priority
        if k in ga:
            action_at_index[k] = ga[k]
        elif wp_name in ga:
            action_at_index[k] = ga[wp_name]

    # Collect all joint angles
    all_qpos = []
    for wp_name in route.waypoints:
        all_qpos.append(store.get_waypoint(wp_name).joint_angles.copy())

    # Extract pre-route gripper action (index 0)
    pre_gripper_action = action_at_index.pop(0, None)

    # Split points: remaining indices with gripper actions
    split_indices = sorted(action_at_index.keys())

    # Build segments
    segments: list[RouteSegment] = []
    start = 0

    for split_k in split_indices:
        # Skip if two consecutive gripper actions at same point
        if split_k == start and segments:
            # Update gripper action on the last segment
            segments[-1].gripper_action = action_at_index[split_k]
            continue
        # Segment [start, split_k] (inclusive)
        seg_qpos = np.array(all_qpos[start : split_k + 1])
        segments.append(RouteSegment(seg_qpos, action_at_index[split_k]))
        start = split_k  # next segment starts from same point

    # Remaining segment [start, end]
    if start < len(all_qpos) - 1:
        seg_qpos = np.array(all_qpos[start:])
        segments.append(RouteSegment(seg_qpos, None))

    # Edge case: entire route has no gripper actions
    if not segments:
        segments.append(RouteSegment(np.array(all_qpos), None))

    logger.info(
        "Split route '%s' into %d segment(s)%s",
        route_name, len(segments),
        " + pre-route gripper" if pre_gripper_action else "",
    )
    return SplitResult(segments=segments, pre_gripper_action=pre_gripper_action)


# ── Execution ──────────────────────────────────────────────────


def execute_trajectory(
    env,
    trajectory: Trajectory,
    gripper_value: float = 1.0,
    time_scale: float = 1.0,
) -> dict:
    """Execute one trajectory segment point by point.

    Sends joint positions to env.step() at the trajectory's timing.
    The gripper value stays constant throughout this segment.

    Args:
        env: Connected FrankaEnv (joint_abs + binary gripper mode).
        trajectory: Planned trajectory to execute.
        gripper_value: Gripper action value for binary mode.
            1.0 = open, 0.0 = close. Only valid for binary gripper mode.
        time_scale: Factor to stretch execution time.
            1.0 = planned speed, 2.0 = half speed, 0.5 = double speed.

    Returns:
        Final observation dict.
    """
    if env.use_gripper and env.gripper_mode != "binary":
        raise ValueError(
            f"execute_trajectory requires binary gripper mode, "
            f"got '{env.gripper_mode}'"
        )
    n = len(trajectory.timestamps)
    gripper_dim = 1 if env.use_gripper else 0

    t_start = time.perf_counter()
    obs = None

    for i in range(n):
        # Build action
        if gripper_dim:
            action = np.concatenate(
                [trajectory.positions[i], [gripper_value]]
            ).astype(np.float32)
        else:
            action = trajectory.positions[i].astype(np.float32)

        obs, _, _, _, _ = env.step(action)

        # Timing: wait until next step's target time (scaled)
        if i < n - 1:
            target = t_start + trajectory.timestamps[i + 1] * time_scale
            remaining = target - time.perf_counter()
            if remaining > 0.002:
                time.sleep(remaining - 0.001)
            while time.perf_counter() < target:
                pass

    return obs


def execute_route(
    env,
    store: WaypointStore,
    route_name: str,
    planner: Optional[TrajectoryPlanner] = None,
    control_hz: float = 200.0,
    time_scale: float = 1.0,
) -> None:
    """Execute a complete route: split -> plan -> execute each segment.

    For each segment:
    1. Plan TOPPRA trajectory
    2. Execute trajectory (robot stops at endpoint)
    3. If segment has gripper action, execute via env.step() (blocking)

    If the route's first waypoint has a gripper action, it is executed
    before any trajectory begins (pre-route action).

    Args:
        env: Connected FrankaEnv (joint_abs + binary gripper mode).
        store: WaypointStore with loaded data.
        route_name: Name of the route to execute.
        planner: TrajectoryPlanner instance (created if None).
        control_hz: Trajectory sampling rate.
        time_scale: Factor to stretch execution time.
            1.0 = planned speed, 2.0 = half speed.
    """
    if planner is None:
        planner = TrajectoryPlanner()

    if env.action_mode != "joint_abs":
        raise ValueError(
            f"execute_route requires joint_abs mode, got '{env.action_mode}'. "
            "Call env.set_action_mode('joint_abs') first."
        )

    result = split_route(store, route_name)
    gripper_value = 1.0  # default: open

    logger.info("Executing route '%s': %d segments", route_name, len(result.segments))

    # Pre-route gripper action (at route start, before any motion)
    if result.pre_gripper_action is not None and env.use_gripper:
        gripper_value = (
            0.0 if result.pre_gripper_action.action == "close" else 1.0
        )
        # Robot is at route start position (set by env.move_to in caller)
        # Send one step to trigger gripper via binary mode
        first_wp_name = store.get_route(route_name).waypoints[0]
        first_qpos = store.get_waypoint(first_wp_name).joint_angles
        action = np.concatenate(
            [first_qpos, [gripper_value]]
        ).astype(np.float32)
        env.step(action)
        logger.info("Pre-route gripper: %s", result.pre_gripper_action.action)

    for seg_idx, segment in enumerate(result.segments):
        # Plan this segment
        traj = planner.plan(segment.waypoints, control_hz=control_hz)

        # Execute trajectory (robot is already at segment start from
        # previous segment's endpoint or from initial move_to)
        logger.info(
            "Segment %d/%d: %d waypoints, %.3f s",
            seg_idx + 1, len(result.segments),
            len(segment.waypoints), traj.timestamps[-1],
        )
        execute_trajectory(env, traj, gripper_value, time_scale=time_scale)

        # Execute gripper action (blocking)
        if segment.gripper_action is not None and env.use_gripper:
            gripper_value = (
                0.0 if segment.gripper_action.action == "close" else 1.0
            )
            # Robot is stationary at endpoint; send one step to trigger
            # blocking gripper action via binary mode
            action = np.concatenate(
                [traj.positions[-1], [gripper_value]]
            ).astype(np.float32)
            env.step(action)
            logger.info("Gripper: %s", segment.gripper_action.action)

    logger.info("Route '%s' completed.", route_name)
