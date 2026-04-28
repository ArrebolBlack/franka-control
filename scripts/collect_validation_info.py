"""Collect environment details for hardware validation.

The script is intentionally safe to run on both the control PC and algorithm PC.
It does not connect to the Franka robot. RealSense probing is opt-in because it
touches USB camera devices.
"""

from __future__ import annotations

import argparse
import json
import platform
import socket
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path
from typing import Any


PACKAGE_NAMES = [
    "franka-control",
    "numpy",
    "scipy",
    "gymnasium",
    "pyzmq",
    "msgpack",
    "torch",
    "torchvision",
    "lerobot",
    "pyrealsense2",
    "opencv-python",
    "matplotlib",
    "pyspacemouse",
    "pynput",
    "pin",
    "toppra",
    "pylibfranka",
    "aiofranka",
]


@dataclass(frozen=True)
class ValidationInfo:
    """Collected host and dependency information."""

    collected_at_utc: str
    hostname: str
    platform: str
    os: str
    kernel: str
    architecture: str
    python: str
    python_executable: str
    git_commit: str
    packages: dict[str, str]
    realsense_devices: list[dict[str, str]]

    def as_dict(self) -> dict[str, Any]:
        return {
            "collected_at_utc": self.collected_at_utc,
            "hostname": self.hostname,
            "platform": self.platform,
            "os": self.os,
            "kernel": self.kernel,
            "architecture": self.architecture,
            "python": self.python,
            "python_executable": self.python_executable,
            "git_commit": self.git_commit,
            "packages": self.packages,
            "realsense_devices": self.realsense_devices,
        }


def _run_git_commit(root: Path) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for name in PACKAGE_NAMES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "not installed"
    return versions


def _probe_realsense() -> list[dict[str, str]]:
    try:
        import pyrealsense2 as rs
    except ImportError:
        return [{"status": "pyrealsense2 not installed"}]

    devices: list[dict[str, str]] = []
    try:
        context = rs.context()
        for device in context.query_devices():
            info = {
                "name": _safe_rs_info(device, rs.camera_info.name),
                "serial": _safe_rs_info(device, rs.camera_info.serial_number),
                "firmware": _safe_rs_info(device, rs.camera_info.firmware_version),
                "usb_type": _safe_rs_info(device, rs.camera_info.usb_type_descriptor),
            }
            devices.append(info)
    except Exception as exc:
        return [{"status": f"RealSense probe failed: {exc}"}]

    if not devices:
        return [{"status": "no RealSense devices detected"}]
    return devices


def _safe_rs_info(device, key) -> str:
    try:
        if device.supports(key):
            return str(device.get_info(key))
    except Exception:
        pass
    return "unknown"


def collect_info(root: Path, probe_realsense: bool = False) -> ValidationInfo:
    """Collect host, Python, git, dependency, and optional camera details."""
    return ValidationInfo(
        collected_at_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        hostname=socket.gethostname(),
        platform=platform.platform(),
        os=f"{platform.system()} {platform.release()}",
        kernel=platform.release(),
        architecture=platform.machine(),
        python=sys.version.replace("\n", " "),
        python_executable=sys.executable,
        git_commit=_run_git_commit(root),
        packages=_package_versions(),
        realsense_devices=_probe_realsense() if probe_realsense else [],
    )


def format_markdown(info: ValidationInfo) -> str:
    """Render collected information as Markdown."""
    lines = [
        "# Validation Environment",
        "",
        "| Item | Value |",
        "|---|---|",
        f"| Collected at UTC | `{info.collected_at_utc}` |",
        f"| Hostname | `{info.hostname}` |",
        f"| Platform | `{info.platform}` |",
        f"| OS | `{info.os}` |",
        f"| Kernel | `{info.kernel}` |",
        f"| Architecture | `{info.architecture}` |",
        f"| Python | `{info.python}` |",
        f"| Python executable | `{info.python_executable}` |",
        f"| Git commit | `{info.git_commit}` |",
        "",
        "## Package Versions",
        "",
        "| Package | Version |",
        "|---|---|",
    ]
    for name, version in info.packages.items():
        lines.append(f"| `{name}` | `{version}` |")

    if info.realsense_devices:
        lines.extend(["", "## RealSense Devices", "", "| Field | Value |", "|---|---|"])
        for idx, device in enumerate(info.realsense_devices, start=1):
            lines.append(f"| Device {idx} | |")
            for key, value in device.items():
                lines.append(f"| `{key}` | `{value}` |")

    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Collect environment details for hardware validation"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--probe-realsense",
        action="store_true",
        help="Probe connected RealSense devices",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root for git metadata (default: auto-detected)",
    )
    args = parser.parse_args()

    info = collect_info(args.root, probe_realsense=args.probe_realsense)
    if args.format == "json":
        print(json.dumps(info.as_dict(), indent=2, sort_keys=True))
    else:
        print(format_markdown(info), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
