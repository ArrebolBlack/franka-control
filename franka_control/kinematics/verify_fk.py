#!/usr/bin/env python3
"""Verify FK correctness by comparing with real robot state.

Usage:
    python -m franka_control.kinematics.verify_fk --robot-ip <CONTROL_MACHINE_IP>
"""

import argparse
import numpy as np
from scipy.spatial.transform import Rotation

from franka_control.robot.robot_client import RobotClient
from franka_control.kinematics import IKSolver


def main():
    parser = argparse.ArgumentParser(description="Verify FK against real robot")
    parser.add_argument("--robot-ip", required=True, help="Control machine IP")
    args = parser.parse_args()

    print("=" * 60)
    print("FK Verification: IKSolver vs Real Robot")
    print("=" * 60)

    # Connect to robot
    print(f"\n[1/4] Connecting to robot at {args.robot_ip}...")
    robot = RobotClient(host=args.robot_ip, port=5555)
    robot.connect()
    robot.start()
    print("✓ Connected")

    # Move to home position
    print("\n[2/4] Moving to home position...")
    home_qpos = np.array([0.0, -0.785, 0.0, -2.356, 0.0, 1.571, 0.785])
    robot.switch("pid")
    robot.move(home_qpos)
    print("✓ At home position")

    # Read real robot state
    print("\n[3/4] Reading real robot state...")
    state = robot.state
    q_real = state["qpos"]
    ee_transform_real = state["ee"]  # 4x4 homogeneous transform
    ee_pos_real = ee_transform_real[:3, 3]
    R_real = ee_transform_real[:3, :3]
    ee_quat_real = Rotation.from_matrix(R_real).as_quat()  # (x, y, z, w)

    print(f"  Joint angles [rad]: {q_real}")
    print(f"  End-effector position [m]: {ee_pos_real}")
    print(f"  End-effector quaternion: {ee_quat_real}")

    # Compute FK with IKSolver
    print("\n[4/4] Computing FK with IKSolver...")

    # Test both fr3v2_hand and fr3v2_link8 (flange)
    solver_hand = IKSolver(ee_frame="fr3v2_hand")
    solver_link8 = IKSolver(ee_frame="fr3v2_link8")

    T_fk_hand = solver_hand.fk(q_real)
    T_fk_link8 = solver_link8.fk(q_real)

    ee_pos_fk_hand = T_fk_hand[:3, 3]
    R_fk_hand = T_fk_hand[:3, :3]

    ee_pos_fk_link8 = T_fk_link8[:3, 3]
    R_fk_link8 = T_fk_link8[:3, :3]

    print(f"  FK (fr3v2_hand) position [m]: {ee_pos_fk_hand}")
    print(f"  FK (fr3v2_link8) position [m]: {ee_pos_fk_link8}")

    # Compare
    print("\n" + "=" * 60)
    print("COMPARISON")
    print("=" * 60)

    # Test fr3v2_hand
    pos_error_hand = np.linalg.norm(ee_pos_fk_hand - ee_pos_real)
    R_diff_hand = R_fk_hand @ R_real.T
    angle_error_hand = np.arccos(np.clip((np.trace(R_diff_hand) - 1) / 2, -1, 1))

    print(f"\n[fr3v2_hand frame]")
    print(f"  Position error: {pos_error_hand * 1000:.2f} mm")
    print(f"  Rotation error: {np.degrees(angle_error_hand):.3f} degrees")

    # Test fr3v2_link8
    pos_error_link8 = np.linalg.norm(ee_pos_fk_link8 - ee_pos_real)
    R_diff_link8 = R_fk_link8 @ R_real.T
    angle_error_link8 = np.arccos(np.clip((np.trace(R_diff_link8) - 1) / 2, -1, 1))

    print(f"\n[fr3v2_link8 frame (flange)]")
    print(f"  Position error: {pos_error_link8 * 1000:.2f} mm")
    print(f"  Rotation error: {np.degrees(angle_error_link8):.3f} degrees")

    # Verdict
    print("\n" + "=" * 60)
    if pos_error_link8 < 0.01 and angle_error_link8 < np.radians(5):
        print("✓ FK VERIFICATION PASSED")
        print("  Real robot reports fr3v2_link8 (flange) frame.")
        print("  Use ee_frame='fr3v2_link8' for IKSolver.")
    elif pos_error_hand < 0.01 and angle_error_hand < np.radians(5):
        print("✓ FK VERIFICATION PASSED")
        print("  Real robot reports fr3v2_hand frame.")
        print("  Use ee_frame='fr3v2_hand' for IKSolver (default).")
    else:
        print("✗ FK VERIFICATION FAILED")
        print("  Neither frame matches. Check URDF model version.")
    print("=" * 60)

    # Cleanup
    robot.close()


if __name__ == "__main__":
    main()
