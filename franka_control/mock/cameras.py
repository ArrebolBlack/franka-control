"""Mock cameras: the CameraManager API without hardware.

Two frame sources per camera:

- ``synthetic``: a generated frame with a moving marker (drawn with OpenCV),
  good for headless smoke tests.
- ``dir:<path>``: preloads every image in a directory and cycles through them,
  resized to the requested resolution.

Frames are returned as uint8 (H, W, 3) RGB, matching ``CameraManager``.
Unlike the real cameras, reads never block.

Usage:
    cameras = MockCameraManager({"front": "synthetic", "wrist": "dir:/tmp/frames"})
    frames = cameras.read_latest()
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

import numpy as np

try:
    import cv2
except ImportError:
    cv2 = None

logger = logging.getLogger(__name__)

_IMAGE_SUFFIXES = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


class _MockCamera:
    """Single mock camera with a CameraManager-compatible read interface."""

    def __init__(self, name: str, source: str, resolution=(640, 480), fps: int = 60):
        if cv2 is None:
            raise ImportError("Mock cameras need OpenCV: pip install opencv-python")
        self._name = name
        self._resolution = (int(resolution[0]), int(resolution[1]))  # (W, H)
        self._fps = int(fps)
        # Private attributes mirror CameraManager's cameras, so callers that
        # extract CameraConfig metadata (collect_episodes.py) keep working.
        self._serial = f"mock-{name}"
        self._depth_enabled = False
        self._lock = threading.Lock()
        self._index = 0
        self._t0 = time.monotonic()
        self._frames: list[np.ndarray] = []

        if source == "synthetic":
            pass
        elif source.startswith("dir:"):
            self._load_dir(Path(source[4:]))
        else:
            raise ValueError(
                f"mock camera '{name}': unknown source '{source}' "
                "(want 'synthetic' or 'dir:<path>')"
            )
        logger.info("Mock camera %s ready (%s, %d frames)",
                    name, source, len(self._frames))

    def _load_dir(self, path: Path) -> None:
        files = (
            sorted(p for p in path.iterdir() if p.suffix.lower() in _IMAGE_SUFFIXES)
            if path.is_dir()
            else []
        )
        if not files:
            raise FileNotFoundError(f"mock camera '{self._name}': no images in {path}")
        w, h = self._resolution
        for f in files:
            img = cv2.imread(str(f), cv2.IMREAD_COLOR)
            if img is None:
                raise RuntimeError(f"mock camera '{self._name}': cannot read {f}")
            img = cv2.resize(img, (w, h), interpolation=cv2.INTER_AREA)
            self._frames.append(np.ascontiguousarray(img[:, :, ::-1]))  # BGR -> RGB

    def _synthetic_frame(self) -> np.ndarray:
        w, h = self._resolution
        frame = np.full((h, w, 3), 40, dtype=np.uint8)
        t = time.monotonic() - self._t0
        phase = (t % 4.0) / 4.0
        cx = int((0.15 + 0.7 * phase) * w)
        cy = int((0.5 + 0.25 * np.sin(2 * np.pi * t / 2.0)) * h)
        radius = max(8, h // 12)
        color = (255, 160, 0) if self._name == "wrist" else (0, 200, 255)
        cv2.circle(frame, (cx, cy), radius, color, -1)
        cv2.putText(frame, f"{self._name}  t={t:6.2f}s", (10, 24),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        return frame

    def _next_frame(self) -> dict:
        with self._lock:
            if self._frames:
                frame = self._frames[self._index % len(self._frames)]
                self._index += 1
            else:
                frame = self._synthetic_frame()
        return {"rgb": frame.copy()}

    def read(self) -> dict:
        """Latest frame; never blocks (unlike RealSense reads)."""
        return self._next_frame()

    def read_nowait(self) -> dict:
        return self._next_frame()


class MockCameraManager:
    """CameraManager-compatible reader over mock cameras.

    Args:
        spec: Mapping of camera name to source ("synthetic" or "dir:<path>").
        resolution: (W, H) frames are produced at.
        fps: Recorded for metadata compatibility; frames are not rate-limited.
    """

    def __init__(self, spec: dict[str, str], resolution=(640, 480), fps: int = 60):
        self._cameras = {
            name: _MockCamera(name, source, resolution=resolution, fps=fps)
            for name, source in spec.items()
        }

    @classmethod
    def from_spec(
        cls, spec: str, resolution=(640, 480), fps: int = 60
    ) -> "MockCameraManager":
        """Parse ``"front=synthetic,wrist=dir:/tmp/frames"``."""
        parsed: dict[str, str] = {}
        for part in spec.split(","):
            part = part.strip()
            if not part:
                continue
            name, _, source = part.partition("=")
            if not name or not source:
                raise ValueError(
                    f"Bad --mock-cameras entry '{part}' "
                    "(want name=synthetic or name=dir:<path>)"
                )
            parsed[name] = source
        if not parsed:
            raise ValueError("--mock-cameras is empty")
        return cls(parsed, resolution=resolution, fps=fps)

    @property
    def camera_names(self) -> list[str]:
        return list(self._cameras)

    def read(self) -> dict[str, dict]:
        return {name: cam.read() for name, cam in self._cameras.items()}

    def read_latest(self) -> dict[str, dict]:
        return {name: cam.read_nowait() for name, cam in self._cameras.items()}

    def close(self) -> None:
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __repr__(self) -> str:
        return f"MockCameraManager(cameras={self.camera_names})"
