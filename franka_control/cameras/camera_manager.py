"""CameraManager — multi-RealSense camera reader.

Each camera runs in a dedicated thread, continuously reading frames
into a Queue(1) (always keeps the latest frame). The main thread
calls read() to get all cameras' latest frames synchronously.

Uses pyrealsense2 for Intel RealSense devices.

Usage:
    cameras = CameraManager({
        "front": {"serial": "xxx", "resolution": (640, 480), "fps": 60, "depth": False},
        "wrist": {"serial": "xxx", "resolution": (640, 480), "fps": 60, "depth": True},
    })
    frames = cameras.read()
    # {"front": {"rgb": (480,640,3) uint8}, "wrist": {"rgb": ..., "depth": (480,640) uint16}}
    cameras.close()
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

import numpy as np

try:
    import pyrealsense2 as rs
except ImportError:
    rs = None

try:
    import yaml
except ImportError:
    yaml = None

logger = logging.getLogger(__name__)

# Default timeout for reading a frame [seconds]
READ_TIMEOUT = 5.0


class _RealSenseCamera:
    """Single RealSense camera reader with background thread.

    Args:
        serial: Device serial number.
        resolution: (width, height) for color stream.
        fps: Frame rate.
        depth: Whether to enable depth stream.
    """

    def __init__(
        self,
        serial: str,
        resolution: tuple[int, int] = (640, 480),
        fps: int = 60,
        depth: bool = False,
    ):
        if rs is None:
            raise ImportError(
                "pyrealsense2 is not installed. "
                "Install with: pip install pyrealsense2"
            )

        self._serial = serial
        self._resolution = resolution
        self._fps = fps
        self._depth_enabled = depth

        # Latest frame buffer
        self._q: Queue[dict] = Queue(maxsize=1)
        self._last_frame: Optional[dict] = None
        self._alive = True

        # Initialize RealSense pipeline
        self._pipeline = rs.pipeline()
        self._config = rs.config()
        self._config.enable_device(serial)
        self._config.enable_stream(
            rs.stream.color, resolution[0], resolution[1],
            rs.format.rgb8, fps,
        )
        if depth:
            self._config.enable_stream(
                rs.stream.depth, resolution[0], resolution[1],
                rs.format.z16, fps,
            )
            self._align = rs.align(rs.stream.color)
        else:
            self._align = None

        self._pipeline.start(self._config)
        logger.info(
            "RealSense camera %s started (%dx%d @ %dfps, depth=%s)",
            serial, resolution[0], resolution[1], fps, depth,
        )

        # Start background thread
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()

    def _read_loop(self) -> None:
        """Continuously read frames from RealSense device."""
        while self._alive:
            try:
                frames = self._pipeline.wait_for_frames(timeout_ms=5000)
            except Exception as e:
                if self._alive:
                    logger.warning("Camera %s read error: %s", self._serial, e)
                    time.sleep(0.01)
                continue

            result = {}

            # Color frame
            color_frame = frames.get_color_frame()
            if color_frame:
                result["rgb"] = np.asarray(color_frame.get_data())

            # Depth frame (aligned to color)
            if self._depth_enabled and self._align is not None:
                aligned_frames = self._align.process(frames)
                depth_frame = aligned_frames.get_depth_frame()
                if depth_frame:
                    result["depth"] = np.asarray(depth_frame.get_data())

            if not result:
                continue

            # Queue(1): discard old, put new
            try:
                self._q.get_nowait()
            except Empty:
                pass
            self._q.put(result)

    def read(self) -> dict:
        """Get latest frame (blocking with timeout).

        Returns:
            dict with "rgb" (H,W,3) uint8 and optionally "depth" (H,W) uint16.
            Returns last known frame on timeout.
        """
        try:
            self._last_frame = self._q.get(timeout=READ_TIMEOUT)
        except Empty:
            logger.warning(
                "Camera %s timeout (%.1fs), returning last frame",
                self._serial, READ_TIMEOUT,
            )
        return self._last_frame or {}

    def read_nowait(self) -> dict:
        """Non-blocking read: return latest available frame without waiting."""
        try:
            self._last_frame = self._q.get_nowait()
        except Empty:
            pass
        return self._last_frame or {}

    def close(self) -> None:
        """Stop thread and release device."""
        self._alive = False
        self._thread.join(timeout=3.0)
        try:
            self._pipeline.stop()
        except Exception as e:
            logger.warning("Camera %s stop error: %s", self._serial, e)
        logger.info("Camera %s closed.", self._serial)


class CameraManager:
    """Multi-camera manager for Intel RealSense devices.

    Each camera runs in a dedicated thread. read() returns the latest
    frame from all cameras.

    Args:
        config: Dict mapping camera name to config dict.
            Each config: {"serial": str, "resolution": (W,H), "fps": int, "depth": bool}
    """

    def __init__(self, config: dict[str, dict]):
        if rs is None:
            raise ImportError(
                "pyrealsense2 is not installed. "
                "Install with: pip install pyrealsense2"
            )

        self._cameras: dict[str, _RealSenseCamera] = {}
        for name, cfg in config.items():
            try:
                self._cameras[name] = _RealSenseCamera(
                    serial=cfg["serial"],
                    resolution=cfg.get("resolution", (640, 480)),
                    fps=cfg.get("fps", 60),
                    depth=cfg.get("depth", cfg.get("enable_depth", False)),
                )
            except Exception as e:
                logger.error("Failed to init camera '%s': %s", name, e)

        if not self._cameras:
            raise RuntimeError("No cameras initialized successfully.")

    def read(self) -> dict[str, dict]:
        """Read latest frame from all cameras.

        Returns:
            {"cam_name": {"rgb": (H,W,3) uint8, "depth": (H,W) uint16}, ...}
        """
        return {name: cam.read() for name, cam in self._cameras.items()}

    def read_latest(self) -> dict[str, dict]:
        """Non-blocking read from all cameras. Returns latest available frames."""
        return {name: cam.read_nowait() for name, cam in self._cameras.items()}

    @property
    def camera_names(self) -> list[str]:
        """List of initialized camera names."""
        return list(self._cameras.keys())

    def close(self) -> None:
        """Stop all camera threads and release devices."""
        for cam in self._cameras.values():
            cam.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return f"CameraManager(cameras={self.camera_names})"

    @classmethod
    def from_yaml(cls, path: str | Path) -> CameraManager:
        """Create CameraManager from a YAML config file.

        YAML format:
            d435:
              serial: "138422075015"
              resolution: [640, 480]
              fps: 60
              enable_depth: false
        """
        if yaml is None:
            raise ImportError("PyYAML is required: pip install pyyaml")
        with open(path) as f:
            cfg = yaml.safe_load(f)
        return cls(cfg)

    @staticmethod
    def list_devices() -> list[dict]:
        """List all connected RealSense devices.

        Returns:
            [{"serial": "xxx", "name": "Intel RealSense D435", "firmware": "xx.xx.xx"}, ...]
        """
        if rs is None:
            return []
        ctx = rs.context()
        return [
            {
                "serial": d.get_info(rs.camera_info.serial_number),
                "name": d.get_info(rs.camera_info.name),
                "firmware": d.get_info(rs.camera_info.firmware_version),
            }
            for d in ctx.devices
        ]
