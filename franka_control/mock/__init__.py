"""Mock stack: run the whole pipeline without hardware.

Drop-in stand-ins for the control-machine services, built by subclassing the
real implementations so the ZMQ/msgpack protocol is inherited, not re-implemented:

- ``MockRobotServer``   — ``RobotServer`` protocol on an aiofranka MuJoCo simulation
- ``MockGripperServer`` — ``GripperServer`` protocol on a simulated Franka Hand
- ``MockCameraManager`` — ``CameraManager`` API on synthetic or directory frames

The mock policy server (``franka_control.mock.policy_server``) speaks the openpi
websocket protocol, so ``deploy_policy.py`` sees the same interface it will use
against a cloud GPU.

Runbook: see ``franka_control/mock/README.md``.
"""

from franka_control.mock.cameras import MockCameraManager
from franka_control.mock.gripper_server import MockGripperServer, SimHand
from franka_control.mock.robot_server import MockRobotServer
from franka_control.mock.sim_controller import SimControllerAdapter

__all__ = [
    "MockCameraManager",
    "MockGripperServer",
    "MockRobotServer",
    "SimControllerAdapter",
    "SimHand",
]
