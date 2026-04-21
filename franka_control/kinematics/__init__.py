"""Kinematics module for Franka Research 3.

Provides forward and inverse kinematics using Pinocchio.
Hardcoded for FR3 family (fr3v2 + Franka Hand by default).

Usage:
    from franka_control.kinematics import IKSolver

    solver = IKSolver()  # Uses bundled fr3v2.urdf
    T = solver.fk(q)     # Forward kinematics: q (7,) -> 4x4 transform
    q, converged = solver.ik(q_init, T_target)  # Inverse kinematics
"""

from franka_control.kinematics.ik_solver import IKSolver

__all__ = ["IKSolver"]
