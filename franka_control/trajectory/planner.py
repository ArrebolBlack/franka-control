"""Trajectory planning with TOPPRA for Franka robot.

Generates time-optimal trajectories through waypoints using TOPPRA,
with chord-length parameterization and joint velocity/acceleration constraints.

Usage:
    planner = TrajectoryPlanner()
    trajectory = planner.plan(waypoints)  # (N, 7) joint angles
    planner.validate(trajectory)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

import numpy as np
import toppra
import toppra.algorithm
import toppra.constraint

from franka_control.envs.franka_env import JOINT_LIMIT_HIGH, JOINT_LIMIT_LOW
from franka_control.trajectory.waypoints import GripperAction, WaypointStore

logger = logging.getLogger(__name__)

# Default velocity/acceleration limits: 80% of aiofranka parameters
# aiofranka vel: [8, 8, 8, 8, 10, 10, 10] rad/s
# aiofranka acc: [4, 4, 4, 4, 5, 5, 5] rad/s^2
DEFAULT_VEL_LIMITS = np.array([6.4, 6.4, 6.4, 6.4, 8.0, 8.0, 8.0])
DEFAULT_ACC_LIMITS = np.array([3.2, 3.2, 3.2, 3.2, 4.0, 4.0, 4.0])


@dataclass
class Trajectory:
    """Sampled time-optimal trajectory through waypoints.

    Attributes:
        timestamps: (N,) time values in seconds.
        positions: (N, 7) joint positions in rad.
        velocities: (N, 7) joint velocities in rad/s.
        waypoint_indices: len = n_waypoints. waypoint_indices[k] is the
            step index closest to the k-th waypoint in the input array.
    """

    timestamps: np.ndarray
    positions: np.ndarray
    velocities: np.ndarray
    waypoint_indices: list[int]


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


class TrajectoryPlanner:
    """TOPPRA-based time-optimal trajectory planner.

    Args:
        vel_limits: Per-joint velocity limits (7,). Defaults to 80% of
            aiofranka parameters.
        acc_limits: Per-joint acceleration limits (7,). Defaults to 80%
            of aiofranka parameters.
    """

    def __init__(
        self,
        vel_limits: Optional[np.ndarray] = None,
        acc_limits: Optional[np.ndarray] = None,
    ):
        self._vel_limits = (
            np.asarray(vel_limits, dtype=np.float64)
            if vel_limits is not None
            else DEFAULT_VEL_LIMITS.copy()
        )
        self._acc_limits = (
            np.asarray(acc_limits, dtype=np.float64)
            if acc_limits is not None
            else DEFAULT_ACC_LIMITS.copy()
        )

    def plan(
        self, waypoints: np.ndarray, control_hz: float = 200.0
    ) -> Trajectory:
        """Plan time-optimal trajectory through waypoints.

        Args:
            waypoints: (N, 7) joint angles. N >= 2.
            control_hz: Sampling rate for the output trajectory.

        Returns:
            Trajectory with uniformly sampled positions/velocities.

        Raises:
            ValueError: If consecutive waypoints are identical, or
                TOPPRA fails to find a feasible trajectory, or
                the result fails safety validation.
        """
        waypoints = np.asarray(waypoints, dtype=np.float64)
        if waypoints.ndim != 2 or waypoints.shape[1] != 7:
            raise ValueError(
                f"waypoints must be (N, 7), got {waypoints.shape}"
            )
        n = len(waypoints)
        if n < 2:
            raise ValueError("Need at least 2 waypoints")

        # Reject consecutive identical waypoints (degenerate for TOPPRA)
        for i in range(1, n):
            if np.allclose(waypoints[i], waypoints[i - 1]):
                raise ValueError(
                    f"Waypoints {i - 1} and {i} are identical. "
                    "Use split_route() to handle dwell/gripper-wait."
                )

        # 1. Chord-length parameterization
        diffs = np.diff(waypoints, axis=0)
        dists = np.linalg.norm(diffs, axis=1)
        ss = np.concatenate([[0.0], np.cumsum(dists)])

        # 2. Geometric path (not-a-knot spline)
        path = toppra.SplineInterpolator(ss, waypoints)

        # 3. Constraints
        constraints = [
            toppra.constraint.JointVelocityConstraint(self._vel_limits),
            toppra.constraint.JointAccelerationConstraint(self._acc_limits),
        ]

        # 4. TOPPRA solve (sd_start=0, sd_end=0 → rest-to-rest)
        instance = toppra.algorithm.TOPPRA(
            constraints, path, solver_wrapper="seidel"
        )
        traj = instance.compute_trajectory(0, 0)
        if traj is None:
            raise ValueError("TOPPRA failed to find feasible trajectory")

        # 5. Uniform sampling at control_hz
        duration = traj.duration
        n_steps = int(duration * control_hz) + 1
        ts = np.linspace(0, duration, n_steps)
        positions = traj(ts, order=0)  # (N, 7)
        velocities = traj(ts, order=1)  # (N, 7)

        # 6. Find waypoint_indices: closest step to each input waypoint
        #    Search monotonically to handle duplicate waypoints correctly.
        waypoint_indices = []
        search_start = 0
        for k in range(n):
            remaining = positions[search_start:]
            if len(remaining) == 0:
                # All remaining waypoints map to the last step
                waypoint_indices.append(len(positions) - 1)
                continue
            step_dists = np.linalg.norm(remaining - waypoints[k], axis=1)
            best = int(np.argmin(step_dists)) + search_start
            waypoint_indices.append(best)
            search_start = min(best + 1, len(positions) - 1)

        trajectory = Trajectory(ts, positions, velocities, waypoint_indices)
        self.validate(trajectory)

        logger.info(
            "Planned trajectory: %d steps, %.3f s, %d waypoints",
            n_steps, duration, n,
        )
        return trajectory

    def validate(self, trajectory: Trajectory) -> None:
        """Check trajectory against joint limits and velocity limits.

        Raises:
            ValueError: If trajectory violates any constraint.
        """
        if np.any(trajectory.positions < JOINT_LIMIT_LOW):
            idx = np.unravel_index(
                np.argmin(trajectory.positions - JOINT_LIMIT_LOW),
                trajectory.positions.shape,
            )
            raise ValueError(
                f"Trajectory exceeds lower joint limit at step {idx[0]}, "
                f"joint {idx[1]}: {trajectory.positions[idx]:.4f} < "
                f"{JOINT_LIMIT_LOW[idx[1]]:.4f}"
            )
        if np.any(trajectory.positions > JOINT_LIMIT_HIGH):
            idx = np.unravel_index(
                np.argmax(trajectory.positions - JOINT_LIMIT_HIGH),
                trajectory.positions.shape,
            )
            raise ValueError(
                f"Trajectory exceeds upper joint limit at step {idx[0]}, "
                f"joint {idx[1]}: {trajectory.positions[idx]:.4f} > "
                f"{JOINT_LIMIT_HIGH[idx[1]]:.4f}"
            )
        max_vel = np.max(np.abs(trajectory.velocities), axis=0)
        if np.any(max_vel > self._vel_limits + 1e-6):
            violating = np.where(max_vel > self._vel_limits + 1e-6)[0]
            raise ValueError(
                f"Trajectory exceeds velocity limits at joint(s) "
                f"{violating.tolist()}: {max_vel[violating].tolist()} > "
                f"{self._vel_limits[violating].tolist()}"
            )


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
) -> list[RouteSegment]:
    """Split a route into planning segments at gripper action points.

    Each segment is planned independently with TOPPRA. Between segments,
    the robot stops at the endpoint and the gripper action is executed
    (blocking) via env.step().

    Example:
        route = [home, above, grasp, lift, carry, release, home]
        gripper_actions = {grasp: close, release: open}

        → Segment 1: [home, above, grasp],     gripper=close
        → Segment 2: [grasp, lift, carry, release], gripper=open
        → Segment 3: [release, home],           gripper=None

    Args:
        store: WaypointStore with loaded data.
        route_name: Name of the route.

    Returns:
        List of RouteSegment.
    """
    route = store.get_route(route_name)
    ga = route.gripper_actions  # {waypoint_name: GripperAction}

    # Build action_at_index: every route index that has a gripper action
    # Same waypoint name can appear multiple times; each gets the action.
    action_at_index: dict[int, GripperAction] = {}
    for k, wp_name in enumerate(route.waypoints):
        if wp_name in ga:
            action_at_index[k] = ga[wp_name]

    # Collect all joint angles
    all_qpos = []
    for wp_name in route.waypoints:
        all_qpos.append(store.get_waypoint(wp_name).joint_angles.copy())

    # Split points: indices with gripper actions
    split_indices = sorted(action_at_index.keys())

    # Build segments
    segments: list[RouteSegment] = []
    start = 0

    for split_k in split_indices:
        if split_k == 0:
            # Gripper on first waypoint: apply before the route starts.
            # Attach to first real segment so execute_route can handle it.
            # (Will be planned and executed as a pre-route action.)
            continue
        # Skip if two consecutive gripper actions at same point
        if split_k == start and split_k > 0:
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
        "Split route '%s' into %d segment(s)", route_name, len(segments)
    )
    return segments


# ── Execution ──────────────────────────────────────────────────


def execute_trajectory(
    env,
    trajectory: Trajectory,
    gripper_value: float = 1.0,
) -> dict:
    """Execute one trajectory segment point by point.

    Sends joint positions to env.step() at the trajectory's timing.
    The gripper value stays constant throughout this segment.

    Args:
        env: Connected FrankaEnv (joint_abs + binary gripper mode).
        trajectory: Planned trajectory to execute.
        gripper_value: Gripper action value for binary mode.
            1.0 = open, 0.0 = close. Only valid for binary gripper mode.

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

        # Timing: wait until next step's target time
        if i < n - 1:
            target = t_start + trajectory.timestamps[i + 1]
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
) -> None:
    """Execute a complete route: split → plan → execute each segment.

    For each segment:
    1. Plan TOPPRA trajectory
    2. Execute trajectory (robot stops at endpoint)
    3. If segment has gripper action, execute via env.step() (blocking)

    Args:
        env: Connected FrankaEnv (joint_abs + binary gripper mode).
        store: WaypointStore with loaded data.
        route_name: Name of the route to execute.
        planner: TrajectoryPlanner instance (created if None).
        control_hz: Trajectory sampling rate.
    """
    if planner is None:
        planner = TrajectoryPlanner()

    if env.action_mode != "joint_abs":
        raise ValueError(
            f"execute_route requires joint_abs mode, got '{env.action_mode}'. "
            "Call env.set_action_mode('joint_abs') first."
        )

    segments = split_route(store, route_name)
    gripper_value = 1.0  # default: open

    logger.info("Executing route '%s': %d segments", route_name, len(segments))

    for seg_idx, segment in enumerate(segments):
        # Plan this segment
        traj = planner.plan(segment.waypoints, control_hz=control_hz)

        # Execute trajectory (robot is already at segment start from
        # previous segment's endpoint or from initial move_to)
        logger.info(
            "Segment %d/%d: %d waypoints, %.3f s",
            seg_idx + 1, len(segments),
            len(segment.waypoints), traj.timestamps[-1],
        )
        execute_trajectory(env, traj, gripper_value)

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
