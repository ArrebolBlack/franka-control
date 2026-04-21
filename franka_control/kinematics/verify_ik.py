#!/usr/bin/env python3
"""Verify IK correctness against real robot.

Moves the robot to several test configurations, reads the real state,
then uses IK to solve back from the end-effector pose. Compares the
IK solution's FK output against the real end-effector pose.

Usage:
    python -m franka_control.kinematics.verify_ik --robot-ip <CONTROL_MACHINE_IP>
"""

import argparse
import numpy as np

from franka_control.robot.robot_client import RobotClient
from franka_control.kinematics import IKSolver

# Test configurations: diverse joint angles within safe range
TEST_CONFIGS = {
    "home": np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785]),
    "left": np.array([0.5, -0.6, 0.2, -2.0, 0.1, 1.4, 0.9]),
    "right": np.array([-0.5, -0.8, -0.2, -2.5, -0.1, 1.6, 0.6]),
    "low": np.array([0.0, 0.0, 0.0, -1.5, 0.0, 1.8, 0.785]),
    "tucked": np.array([0.0, -1.2, 0.0, -2.8, 0.0, 1.2, 0.785]),
}


def main():
    parser = argparse.ArgumentParser(description="Verify IK against real robot")
    parser.add_argument("--robot-ip", required=True, help="Control machine IP")
    args = parser.parse_args()

    print("=" * 60)
    print("IK Verification: IKSolver vs Real Robot")
    print("=" * 60)

    solver = IKSolver()

    robot = RobotClient(host=args.robot_ip, port=5555)
    robot.connect()
    robot.start()
    robot.switch("pid")
    print("✓ Connected\n")

    results = []

    for name, q_target in TEST_CONFIGS.items():
        print(f"--- Config: {name} ---")

        # Move robot to target configuration
        robot.move(q_target)
        state = robot.state
        q_real = state["qpos"]
        T_real = state["ee"]

        # FK from real joint angles (sanity check)
        T_fk = solver.fk(q_real)
        fk_pos_err = np.linalg.norm(T_fk[:3, 3] - T_real[:3, 3])

        # IK: solve from real end-effector pose, starting from home
        q_home = TEST_CONFIGS["home"]
        q_ik, converged = solver.ik(q_home, T_real)

        # Verify IK solution by computing its FK
        T_ik_fk = solver.fk(q_ik)
        ik_pos_err = np.linalg.norm(T_ik_fk[:3, 3] - T_real[:3, 3])
        R_diff = T_ik_fk[:3, :3] @ T_real[:3, :3].T
        ik_rot_err = np.arccos(np.clip((np.trace(R_diff) - 1) / 2, -1, 1))

        # Joint-space error (may differ due to redundancy)
        q_err = np.max(np.abs(q_ik - q_real))

        results.append({
            "name": name,
            "converged": converged,
            "ik_pos_err_mm": ik_pos_err * 1000,
            "ik_rot_err_deg": np.degrees(ik_rot_err),
            "max_q_err_deg": np.degrees(q_err),
            "fk_pos_err_mm": fk_pos_err * 1000,
        })

        status = "✓" if converged else "✗"
        print(f"  {status} Converged: {converged}")
        print(f"    FK sanity check:  {fk_pos_err * 1000:.2f} mm")
        print(f"    IK position err:  {ik_pos_err * 1000:.2f} mm")
        print(f"    IK rotation err:  {np.degrees(ik_rot_err):.3f} deg")
        print(f"    Max joint err:    {np.degrees(q_err):.2f} deg")
        print()

    # Move back to home
    robot.move(TEST_CONFIGS["home"])
    robot.close()

    # Summary
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"{'Config':<10} {'Conv':>5} {'Pos[mm]':>8} {'Rot[deg]':>9} {'Jnt[deg]':>9}")
    print("-" * 45)

    all_passed = True
    for r in results:
        status = "✓" if r["converged"] else "✗"
        print(f"{r['name']:<10} {status:>5} {r['ik_pos_err_mm']:>8.2f} "
              f"{r['ik_rot_err_deg']:>9.3f} {r['max_q_err_deg']:>9.2f}")
        if not r["converged"] or r["ik_pos_err_mm"] > 1.0 or r["ik_rot_err_deg"] > 1.0:
            all_passed = False

    print()
    if all_passed:
        print("✓ IK VERIFICATION PASSED")
        print("  All configs converged with < 1mm position and < 1° rotation error.")
    else:
        print("✗ IK VERIFICATION FAILED")
        print("  Some configs did not converge or exceeded error tolerance.")
    print("=" * 60)


if __name__ == "__main__":
    main()
