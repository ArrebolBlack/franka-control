#!/usr/bin/env python3
"""List connected RealSense cameras and generate camera YAML snippets.

Usage:
    python -m franka_control.cameras.list_cameras
    python -m franka_control.cameras.list_cameras --format yaml
"""

from __future__ import annotations

import argparse
import json
import re

from franka_control.cameras.camera_manager import CameraManager


def _camera_name(device: dict, index: int) -> str:
    model = str(device.get("name", "")).lower()
    match = re.search(r"\bd(\d{3}[a-z]?)\b", model)
    if match:
        return f"d{match.group(1)}"
    return f"camera_{index}"


def _yaml_snippet(devices: list[dict], width: int, height: int, fps: int) -> str:
    lines = []
    used_names: dict[str, int] = {}
    for idx, device in enumerate(devices, 1):
        base_name = _camera_name(device, idx)
        count = used_names.get(base_name, 0) + 1
        used_names[base_name] = count
        name = base_name if count == 1 else f"{base_name}_{count}"
        lines.extend(
            [
                f"{name}:",
                f"  serial: \"{device.get('serial', '')}\"",
                f"  resolution: [{width}, {height}]",
                f"  fps: {fps}",
                "  enable_depth: false",
                "",
            ]
        )
    return "\n".join(lines).rstrip()


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="List connected RealSense cameras for config/cameras.yaml"
    )
    parser.add_argument(
        "--format",
        choices=["text", "yaml", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--resolution",
        nargs=2,
        type=int,
        metavar=("WIDTH", "HEIGHT"),
        default=(640, 480),
        help="Resolution to use in YAML output (default: 640 480)",
    )
    parser.add_argument(
        "--fps",
        type=int,
        default=60,
        help="FPS to use in YAML output (default: 60)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    devices = CameraManager.list_devices()

    if args.format == "json":
        print(json.dumps(devices, indent=2))
        return

    if not devices:
        print("No RealSense cameras found.")
        print("\nTroubleshooting:")
        print("  - Check USB connection")
        print("  - Run: rs-enumerate-devices")
        print("  - Install: pip install pyrealsense2")
        return

    width, height = args.resolution
    if args.format == "yaml":
        print(_yaml_snippet(devices, width, height, args.fps))
        return

    print(f"Found {len(devices)} RealSense camera(s):\n")
    for i, dev in enumerate(devices, 1):
        print(f"{i}. {dev['name']}")
        print(f"   Serial:   {dev['serial']}")
        print(f"   Firmware: {dev['firmware']}")
        print()

    print("Suggested config/cameras.yaml snippet:")
    print()
    print(_yaml_snippet(devices, width, height, args.fps))
    print()
    print("Use it with:")
    print("  python -m franka_control.scripts.collect_episodes --cameras config/cameras.yaml ...")


if __name__ == "__main__":
    main()
