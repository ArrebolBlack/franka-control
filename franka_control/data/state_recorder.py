"""Background state stream recorder for dual-thread data collection."""

import logging
import queue
import threading
import time

import numpy as np
from scipy.spatial.transform import Rotation

logger = logging.getLogger(__name__)


def streaming_to_obs(streaming_state: dict, gripper_width: float) -> dict:
    """Convert RobotClient streaming state to obs dict for DataCollector."""
    qpos = streaming_state["qpos"]
    qvel = streaming_state["qvel"]
    ee = streaming_state["ee"].reshape(4, 4)
    jac = streaming_state["jac"].reshape(6, 7)
    torque = streaming_state["last_torque"]

    return {
        "joint_pos": qpos.astype(np.float32),
        "joint_vel": qvel.astype(np.float32),
        "joint_torque": torque.astype(np.float32),
        "ee_pos": ee[:3, 3].astype(np.float32),
        "ee_quat": Rotation.from_matrix(ee[:3, :3]).as_quat().astype(np.float32),
        "ee_vel": (jac @ qvel).astype(np.float32),
        "gripper_width": np.array([gripper_width], dtype=np.float32),
    }


class StateStreamRecorder:
    """Background thread that polls streaming state at target FPS.

    Reads from RobotClient.state (thread-safe PULL socket) and queues
    observation dicts for the main recording loop to drain.

    Args:
        robot_client: RobotClient instance (must have thread-safe .state).
        fps: Target polling frequency.
        buffer_seconds: Queue capacity in seconds of frames.
    """

    def __init__(self, robot_client_fn, fps: int = 60, buffer_seconds: float = 5.0):
        self._get_robot = robot_client_fn
        self._fps = fps
        self._dt = 1.0 / fps
        self._queue = queue.Queue(maxsize=int(fps * buffer_seconds))
        self._stop = threading.Event()
        self._gripper_width = 0.0
        self._thread = None

    @property
    def gripper_width(self) -> float:
        return self._gripper_width

    @gripper_width.setter
    def gripper_width(self, value: float) -> None:
        self._gripper_width = value

    def start(self) -> None:
        """Start the background polling thread."""
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Stop the background polling thread."""
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=timeout)
            self._thread = None

    def drain(self) -> list[dict]:
        """Return all accumulated observations and clear the queue."""
        frames = []
        while not self._queue.empty():
            frames.append(self._queue.get_nowait())
        return frames

    def _run(self) -> None:
        while not self._stop.is_set():
            t0 = time.perf_counter()
            robot = self._get_robot()
            if robot is None:
                time.sleep(self._dt)
                continue
            streaming = robot.state
            if streaming and "qpos" in streaming:
                obs = streaming_to_obs(streaming, self._gripper_width)
                try:
                    self._queue.put_nowait(obs)
                except queue.Full:
                    pass
            elapsed = time.perf_counter() - t0
            if elapsed < self._dt:
                time.sleep(self._dt - elapsed)
