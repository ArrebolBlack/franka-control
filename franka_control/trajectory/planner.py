"""Trajectory planning with TOPPRA for Franka robot.

Generates time-optimal trajectories through waypoints using TOPPRA,
with chord-length parameterization and joint velocity/acceleration constraints.

Zero internal project dependencies — only requires numpy and toppra.

Usage:
    planner = TrajectoryPlanner()
    trajectory = planner.plan(waypoints)  # (N, 7) joint angles
    planner.validate(trajectory)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import toppra
import toppra.algorithm
import toppra.constraint

logger = logging.getLogger(__name__)

# Default velocity/acceleration limits: 80% of aiofranka parameters
# aiofranka vel: [8, 8, 8, 8, 10, 10, 10] rad/s
# aiofranka acc: [4, 4, 4, 4, 5, 5, 5] rad/s^2
DEFAULT_VEL_LIMITS = np.array([6.4, 6.4, 6.4, 6.4, 8.0, 8.0, 8.0])
DEFAULT_ACC_LIMITS = np.array([3.2, 3.2, 3.2, 3.2, 4.0, 4.0, 4.0])

# Franka Research 3 joint limits [rad]
# Source: https://frankaemika.github.io/docs/control_parameters.html
JOINT_LIMIT_LOW = np.array(
    [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973]
)
JOINT_LIMIT_HIGH = np.array(
    [2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973]
)


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

        # 4. TOPPRA solve (sd_start=0, sd_end=0 -> rest-to-rest)
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

    def validate(
        self,
        trajectory: Trajectory,
        joint_limits_low: Optional[np.ndarray] = None,
        joint_limits_high: Optional[np.ndarray] = None,
    ) -> None:
        """Check trajectory against joint limits and velocity limits.

        Args:
            trajectory: Trajectory to validate.
            joint_limits_low: Lower joint limits (7,). Defaults to
                Franka Research 3 limits.
            joint_limits_high: Upper joint limits (7,). Defaults to
                Franka Research 3 limits.

        Raises:
            ValueError: If trajectory violates any constraint.
        """
        low = joint_limits_low if joint_limits_low is not None else JOINT_LIMIT_LOW
        high = joint_limits_high if joint_limits_high is not None else JOINT_LIMIT_HIGH

        if np.any(trajectory.positions < low):
            idx = np.unravel_index(
                np.argmin(trajectory.positions - low),
                trajectory.positions.shape,
            )
            raise ValueError(
                f"Trajectory exceeds lower joint limit at step {idx[0]}, "
                f"joint {idx[1]}: {trajectory.positions[idx]:.4f} < "
                f"{low[idx[1]]:.4f}"
            )
        if np.any(trajectory.positions > high):
            idx = np.unravel_index(
                np.argmax(trajectory.positions - high),
                trajectory.positions.shape,
            )
            raise ValueError(
                f"Trajectory exceeds upper joint limit at step {idx[0]}, "
                f"joint {idx[1]}: {trajectory.positions[idx]:.4f} > "
                f"{high[idx[1]]:.4f}"
            )
        max_vel = np.max(np.abs(trajectory.velocities), axis=0)
        if np.any(max_vel > self._vel_limits * 1.01):
            violating = np.where(max_vel > self._vel_limits * 1.01)[0]
            raise ValueError(
                f"Trajectory exceeds velocity limits at joint(s) "
                f"{violating.tolist()}: {max_vel[violating].tolist()} > "
                f"{self._vel_limits[violating].tolist()}"
            )
