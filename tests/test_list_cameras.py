"""Unit tests for RealSense camera listing helpers."""

from franka_control.cameras.list_cameras import _camera_name, _yaml_snippet


def test_camera_name_from_realsense_model():
    assert _camera_name({"name": "Intel RealSense D405"}, 1) == "d405"
    assert _camera_name({"name": "Intel RealSense D435I"}, 2) == "d435i"
    assert _camera_name({"name": "Unknown Camera"}, 3) == "camera_3"


def test_yaml_snippet_uses_serials_and_unique_names():
    devices = [
        {
            "name": "Intel RealSense D435",
            "serial": "111",
            "firmware": "5.0",
        },
        {
            "name": "Intel RealSense D435",
            "serial": "222",
            "firmware": "5.0",
        },
    ]

    snippet = _yaml_snippet(devices, width=640, height=480, fps=30)

    assert "d435:" in snippet
    assert "d435_2:" in snippet
    assert 'serial: "111"' in snippet
    assert 'serial: "222"' in snippet
    assert "resolution: [640, 480]" in snippet
    assert "fps: 30" in snippet
