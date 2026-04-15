"""Execute a planned trajectory on Franka robot.

Loads waypoints and routes from YAML, plans time-optimal trajectories
with TOPPRA, and executes them on the real robot.

Usage:
    # Plan only (no robot connection)
    python -m franka_control.scripts.run_trajectory \\
        --waypoints config/waypoints.yaml \\
        --route pick_place \\
        --dry-run

    # Execute on robot
    python -m franka_control.scripts.run_trajectory \\
        --robot-ip 172.16.0.2 \\
        --gripper-host 172.16.0.2 \\
        --waypoints config/waypoints.yaml \\
        --route pick_place

    # Loop execution
    python -m franka_control.scripts.run_trajectory \\
        --robot-ip 172.16.0.2 \\
        --waypoints config/waypoints.yaml \\
        --route pick_place \\
        --loop
"""

from __future__ import annotations

import argparse
import logging
import time

import numpy as np

from franka_control.envs.franka_env import FrankaEnv
from franka_control.trajectory.planner import (
    TrajectoryPlanner,
    execute_route,
    split_route,
)
from franka_control.trajectory.waypoints import WaypointStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Execute a planned trajectory on Franka robot"
    )
    parser.add_argument("--robot-ip", default=None, help="Control machine IP")
    parser.add_argument("--gripper-host", default=None,
                        help="Gripper server host (default: same as --robot-ip)")
    parser.add_argument("--gripper-port", type=int, default=5556)
    parser.add_argument(
        "--waypoints", default="config/waypoints.yaml",
        help="Waypoint YAML file (default: config/waypoints.yaml)",
    )
    parser.add_argument("--route", required=True, help="Route name to execute")
    parser.add_argument(
        "--control-hz", type=float, default=200.0,
        help="Trajectory sampling rate [Hz] (default: 200)",
    )
    parser.add_argument(
        "--vel-scale", type=float, default=1.0,
        help="Velocity limit scale factor (default: 1.0)",
    )
    parser.add_argument(
        "--acc-scale", type=float, default=1.0,
        help="Acceleration limit scale factor (default: 1.0)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Plan only, print trajectory info, do not connect to robot",
    )
    parser.add_argument(
        "--loop", action="store_true",
        help="Repeat execution until Ctrl+C",
    )
    args = parser.parse_args()

    # Default gripper_host to robot_ip
    if args.gripper_host is None and args.robot_ip is not None:
        args.gripper_host = args.robot_ip

    # Load waypoints
    store = WaypointStore()
    store.load(args.waypoints)
    logger.info(
        "Loaded %d waypoints, %d routes from %s",
        len(store.list_waypoint_names()),
        len(store.list_route_names()),
        args.waypoints,
    )

    if not store.has_route(args.route):
        logger.error("Route '%s' not found.", args.route)
        return

    # Create planner
    from franka_control.trajectory.planner import DEFAULT_VEL_LIMITS, DEFAULT_ACC_LIMITS
    planner = TrajectoryPlanner(
        vel_limits=DEFAULT_VEL_LIMITS * args.vel_scale,
        acc_limits=DEFAULT_ACC_LIMITS * args.acc_scale,
    )

    # Plan all segments
    segments = split_route(store, args.route)
    trajs = []
    for i, seg in enumerate(segments):
        traj = planner.plan(seg.waypoints, control_hz=args.control_hz)
        trajs.append(traj)
        logger.info(
            "Segment %d/%d: %d waypoints, %.3f s, %d steps%s",
            i + 1, len(segments),
            len(seg.waypoints), traj.timestamps[-1], len(traj.timestamps),
            f", gripper={seg.gripper_action.action}" if seg.gripper_action else "",
        )

    total_time = sum(t.timestamps[-1] for t in trajs)
    logger.info("Total trajectory time: %.3f s", total_time)

    if args.dry_run:
        _print_trajectory_details(segments, trajs, store)
        return

    # Validate robot connection
    if args.robot_ip is None:
        logger.error("--robot-ip is required for execution. Use --dry-run for planning only.")
        return

    # Execute
    use_gripper = args.gripper_host is not None
    env = FrankaEnv(
        robot_ip=args.robot_ip,
        gripper_host=args.gripper_host,
        gripper_port=args.gripper_port,
        action_mode="joint_abs",
        gripper_mode="binary" if use_gripper else "continuous",
    )

    try:
        logger.info("Connecting to robot...")
        env.reset()

        run_count = 0
        while True:
            run_count += 1
            logger.info("=== Run %d ===", run_count)

            # Move to route start
            first_wp_name = store.get_route(args.route).waypoints[0]
            first_qpos = store.get_waypoint(first_wp_name).joint_angles
            logger.info("Moving to start position '%s'...", first_wp_name)
            env.move_to(first_qpos)

            # Execute route
            execute_route(env, store, args.route, planner, args.control_hz)

            logger.info("Run %d completed.", run_count)

            if not args.loop:
                break

            logger.info("Looping in 3 seconds... (Ctrl+C to stop)")
            time.sleep(3.0)

    except KeyboardInterrupt:
        logger.info("Interrupted.")
    finally:
        env.close()
        logger.info("Done. Total runs: %d", run_count)


def _print_trajectory_details(segments, trajs, store):
    """Print detailed trajectory info for dry-run."""
    for i, (seg, traj) in enumerate(zip(segments, trajs)):
        print(f"\n{'='*60}")
        print(f"Segment {i + 1}/{len(segments)}")
        print(f"  Waypoints: {len(seg.waypoints)}")
        print(f"  Duration:  {traj.timestamps[-1]:.3f} s")
        print(f"  Steps:     {len(traj.timestamps)}")
        print(f"  Waypoint indices: {traj.waypoint_indices}")

        if seg.gripper_action:
            print(f"  Gripper: {seg.gripper_action.action} (blocking)")

        # Position range per joint
        for j in range(7):
            lo = traj.positions[:, j].min()
            hi = traj.positions[:, j].max()
            print(f"  Joint {j+1}: [{lo:.4f}, {hi:.4f}] rad")

        # Max velocity per joint
        max_vel = np.max(np.abs(traj.velocities), axis=0)
        print(f"  Max velocity: {np.round(max_vel, 3).tolist()} rad/s")

    print(f"\n{'='*60}")
    total = sum(t.timestamps[-1] for t in trajs)
    print(f"Total time: {total:.3f} s ({len(segments)} segments)")


if __name__ == "__main__":
    main()
