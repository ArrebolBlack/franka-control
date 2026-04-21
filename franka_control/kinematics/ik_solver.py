"""Forward and inverse kinematics for Franka Research 3 using Pinocchio.

Hardcoded for FR3 family (fr3, fr3v2, fr3v2_1).
Default URDF: assets/fr3v2.urdf bundled with this package.
Default end-effector frame: fr3v2_link8 (flange), matching real robot state.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import numpy as np
import pinocchio as pin

# Franka Research 3 joint limits [rad]
# Source: https://frankaemika.github.io/docs/control_parameters.html
JOINT_LIMIT_LOW = np.array(
    [-2.8973, -1.7628, -2.8973, -3.0718, -2.8973, -0.0175, -2.8973],
    dtype=np.float64,
)
JOINT_LIMIT_HIGH = np.array(
    [2.8973, 1.7628, 2.8973, -0.0698, 2.8973, 3.7525, 2.8973],
    dtype=np.float64,
)

# Default URDF path (relative to this file)
_DEFAULT_URDF = Path(__file__).parent / "assets" / "fr3v2.urdf"


class IKSolver:
    """Forward and inverse kinematics solver for Franka Research 3.

    Defaults to fr3v2 + flange (fr3v2_link8) configuration. URDF and meshes
    are bundled in the assets/ directory.

    Args:
        urdf_path: Path to URDF file. If None, uses bundled fr3v2.urdf.
        ee_frame: End-effector frame name. Default: "fr3v2_link8" (flange).
    """

    def __init__(
        self,
        urdf_path: Optional[str] = None,
        ee_frame: str = "fr3v2_link8",
    ):
        if urdf_path is None:
            urdf_path = str(_DEFAULT_URDF)

        if not os.path.exists(urdf_path):
            raise FileNotFoundError(
                f"URDF not found: {urdf_path}. "
                f"Expected bundled URDF at {_DEFAULT_URDF}"
            )

        # Load URDF from the assets directory (mesh paths are relative)
        self.model = pin.buildModelFromUrdf(urdf_path)
        self.data = self.model.createData()

        # Validate end-effector frame
        if not self.model.existFrame(ee_frame):
            available = [self.model.frames[i].name for i in range(len(self.model.frames))]
            raise ValueError(
                f"End-effector frame '{ee_frame}' not found in URDF. "
                f"Available frames: {available}"
            )

        self.frame_id = self.model.getFrameId(ee_frame)
        self.ee_frame = ee_frame

    def fk(self, q: np.ndarray) -> np.ndarray:
        """Compute forward kinematics: q (7,) -> 4x4 homogeneous transform.

        Args:
            q: Joint angles for the 7-DOF arm, shape (7,). Gripper joints
               are automatically set to 0 (closed).

        Returns:
            4x4 homogeneous transformation matrix of the end-effector.
        """
        q = np.asarray(q, dtype=np.float64)
        if q.shape != (7,):
            raise ValueError(f"Expected q shape (7,), got {q.shape}")

        # Pad with gripper joints (both set to 0 = closed)
        q_full = np.zeros(self.model.nq)
        q_full[:7] = q

        pin.framesForwardKinematics(self.model, self.data, q_full)
        return self.data.oMf[self.frame_id].homogeneous.copy()

    def ik(
        self,
        q_init: np.ndarray,
        target_ee: np.ndarray,
        tol: float = 1e-4,
        max_iter: int = 100,
    ) -> tuple[np.ndarray, bool]:
        """Solve inverse kinematics by Jacobian pseudo-inverse iteration.

        Args:
            q_init: Initial joint configuration for the 7-DOF arm, shape (7,).
            target_ee: Target end-effector pose as 4x4 homogeneous transform.
            tol: Convergence threshold on 6D pose error.
            max_iter: Maximum number of iterations.

        Returns:
            (q, converged): Joint solution (7,) and whether the solver converged.
        """
        q_init = np.asarray(q_init, dtype=np.float64)
        if q_init.shape != (7,):
            raise ValueError(f"Expected q_init shape (7,), got {q_init.shape}")

        target_ee = np.asarray(target_ee, dtype=np.float64)
        target_se3 = pin.SE3(target_ee[:3, :3], target_ee[:3, 3])

        # Work in full configuration space (7 arm + 2 gripper)
        q_full = np.zeros(self.model.nq)
        q_full[:7] = q_init

        for _ in range(max_iter):
            pin.framesForwardKinematics(self.model, self.data, q_full)
            current = self.data.oMf[self.frame_id]
            error = pin.log6(current.actInv(target_se3)).vector

            if np.linalg.norm(error) < tol:
                return q_full[:7], True

            J = pin.computeFrameJacobian(
                self.model,
                self.data,
                q_full,
                self.frame_id,
                pin.LOCAL,
            )
            # Only use Jacobian columns for the arm (first 7 DOF)
            J_arm = J[:, :7]
            dq_arm = np.linalg.lstsq(J_arm, error, rcond=None)[0]
            q_full[:7] += dq_arm
            q_full[:7] = np.clip(q_full[:7], JOINT_LIMIT_LOW, JOINT_LIMIT_HIGH)

        return q_full[:7], False
