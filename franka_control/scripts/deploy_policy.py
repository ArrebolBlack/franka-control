"""Deploy a policy (VLA) on the Franka robot.

Companion to ``collect_episodes.py``: the same robot plumbing (``FrankaEnv`` +
``RobotClient``/``GripperClient``), but actions come from a remote policy
server instead of teleoperation, and nothing is recorded.

Policy protocol: the openpi websocket server, spoken through the official
``openpi_client.websocket_client_policy`` — the same client code that talks to
``openpi/scripts/serve_policy.py`` on a cloud GPU.

Observation dict sent to the server (keys follow the openpi/pi0 convention):

    observation/state        float32 (8,)   q0..q6 + gripper_width
    observation/image        uint8 (S,S,3)  front camera, RGB
    observation/wrist_image  uint8 (S,S,3)  wrist camera, RGB (zeros if none)
    prompt                   str

The server replies with ``{"actions": (H, D) array, "server_timing": ...}``;
``D`` must equal the env action dimension (7 for ``ee_delta`` + gripper, i.e.
``[dx, dy, dz, drx, dry, drz, gripper]``). An openpi Franka policy config must
consume exactly these keys.

The policy server usually runs on a cloud GPU behind an SSH tunnel: bring it
up with ``scripts/cloud_tunnel.sh up`` (see docs/cloud_gpu.md), then point
``--policy-host 127.0.0.1`` at the tunnel. Dropped connections are reconnected
and retried with a fresh observation for ``--infer-retry-timeout`` seconds
before the loop gives up and stops safely.

Usage (stage 1, no hardware — see franka_control/mock/README.md):

    python -m franka_control.scripts.deploy_policy \\
        --robot-ip 127.0.0.1 --gripper-host 127.0.0.1 \\
        --policy-host 127.0.0.1 --prompt "pick cube" \\
        --mock-cameras front=synthetic,wrist=synthetic \\
        --fps 30 --duration 60 --log-jsonl /tmp/stage1.jsonl
"""

from __future__ import annotations

import argparse
import json
import logging
import signal
import socket
import time
from collections import deque
from typing import Optional, Callable

import numpy as np

from franka_control.cameras import CameraManager
from franka_control.envs import FrankaEnv
from franka_control.mock.cameras import MockCameraManager
from franka_control.scripts.collect_episodes import Display

from openpi_client import image_tools
from openpi_client import websocket_client_policy as _ws_policy

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def _pick_cameras(args):
    """Build the camera source: real RealSense, mock, or none."""
    if args.no_camera:
        logger.info("Cameras disabled (--no-camera)")
        return None
    if args.mock_cameras:
        cameras = MockCameraManager.from_spec(args.mock_cameras)
        logger.info("Mock cameras: %s", cameras.camera_names)
        return cameras
    cameras = CameraManager.from_yaml(args.cameras)
    logger.info("Cameras: %s", cameras.camera_names)
    return cameras


def _resolve_camera_names(cameras, front_arg, wrist_arg):
    """Map cameras to the policy's front/wrist slots."""
    if cameras is None:
        return None, None
    names = cameras.camera_names
    front = front_arg or (names[0] if names else None)
    wrist = wrist_arg or (names[1] if len(names) > 1 else None)
    return front, wrist


def _build_policy_obs(env, frames, front_name, wrist_name, image_size, prompt):
    """Assemble the openpi observation dict from the env and camera frames."""
    obs = env.get_observation()
    gripper_width = obs.get("gripper_width")
    if gripper_width is None:
        gripper_width = np.zeros(1, dtype=np.float32)
    state = np.concatenate(
        [np.asarray(obs["joint_pos"], dtype=np.float32), np.asarray(gripper_width, dtype=np.float32)]
    )

    front = frames.get(front_name, {}).get("rgb") if front_name else None
    wrist = frames.get(wrist_name, {}).get("rgb") if wrist_name else None
    if front is None:
        front = np.zeros((image_size or 256, image_size or 256, 3), dtype=np.uint8)
    if wrist is None:
        wrist = np.zeros_like(front)
    if image_size > 0:
        front = image_tools.convert_to_uint8(
            image_tools.resize_with_pad(front, image_size, image_size)
        )
        wrist = image_tools.convert_to_uint8(
            image_tools.resize_with_pad(wrist, image_size, image_size)
        )

    return {
        "observation/state": state,
        "observation/image": front,
        "observation/wrist_image": wrist,
        "prompt": prompt,
    }


def _wait_for_policy_server(host: str, port: int, timeout: float) -> None:
    """Fail fast (with a clear message) when the policy server is unreachable.

    The openpi client retries silently every 5 s, which hides a missing
    server (or a dead tunnel); this pre-check turns that into an error.
    """
    deadline = time.monotonic() + timeout
    while True:
        try:
            with socket.create_connection((host, port), timeout=1.0):
                return
        except OSError as exc:
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"policy server unreachable at {host}:{port} after "
                    f"{timeout:.0f}s ({exc}). Start the server; if it runs on a "
                    "cloud GPU, check the tunnel: scripts/cloud_tunnel.sh check"
                ) from exc
            time.sleep(0.5)


class ResilientPolicyClient:
    """openpi websocket client with reconnect + retry around ``infer()``.

    The cloud link can drop mid-episode (SSH tunnel, network). Instead of
    crashing the deploy loop, a failed inference drops the connection, waits
    with backoff and retries with a fresh observation until ``retry_timeout``
    runs out — then raises. While it retries the loop blocks; the robot holds
    its last target. ``retry_timeout=0`` disables retrying (fail fast).

    Only connection-type failures are retried: when the server itself answers
    with an error traceback (openpi raises ``RuntimeError`` for that), the
    failure is deterministic — e.g. an observation-key mismatch — and is
    re-raised immediately instead of burning the retry budget.

    ``client_factory`` / ``wait_for_server`` exist for tests; leave them None.
    """

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float = 30.0,
        retry_timeout: float = 120.0,
        client_factory: Optional[Callable[[], object]] = None,
        wait_for_server: Optional[Callable[[float], None]] = None,
    ):
        self._connect_timeout = connect_timeout
        self._retry_timeout = retry_timeout
        self._client_factory = client_factory or (
            lambda: _ws_policy.WebsocketClientPolicy(host=host, port=port)
        )
        self._wait_for_server = wait_for_server or (
            lambda timeout: _wait_for_policy_server(host, port, timeout)
        )
        self._client = None

    def connect(self) -> dict:
        """Wait for the server, open the connection, return its metadata."""
        self._wait_for_server(self._connect_timeout)
        self._client = self._client_factory()
        return self._client.get_server_metadata()

    def infer(self, obs_builder: Callable[[], dict]) -> dict:
        """Inference with bounded reconnect/retry.

        ``obs_builder`` is called once up front and again after every failure,
        so retries use a fresh observation instead of a stale one.
        """
        obs = obs_builder()
        deadline = time.monotonic() + self._retry_timeout
        attempt = 0
        while True:
            attempt += 1
            try:
                if self._client is None:
                    remaining = max(0.5, deadline - time.monotonic())
                    self._wait_for_server(min(5.0, remaining))
                    self._client = self._client_factory()
                    if attempt > 1:
                        logger.info("Policy connection re-established")
                return self._client.infer(obs)
            except Exception as exc:
                self._client = None
                if isinstance(exc, RuntimeError):
                    # The server answered with a traceback string (openpi
                    # client raises RuntimeError for that): deterministic,
                    # retrying would only repeat it. Connection problems are
                    # the retryable failures.
                    raise
                if time.monotonic() >= deadline:
                    raise RuntimeError(
                        f"policy server unreachable after {self._retry_timeout:.0f}s "
                        f"({attempt} attempts); last error: {exc}"
                    ) from exc
                delay = min(5.0, 0.5 * 2 ** min(attempt - 1, 4))
                logger.warning(
                    "Policy infer failed (attempt %d): %s — retrying in %.1fs "
                    "(tunnel down? run scripts/cloud_tunnel.sh check)",
                    attempt, exc, delay,
                )
                time.sleep(delay)
                obs = obs_builder()


def _parse_args():
    parser = argparse.ArgumentParser(description="Deploy a policy on the Franka robot")

    # ── Robot ────────────────────────────────────────────────────
    parser.add_argument("--robot-ip", required=True,
                        help="Control machine IP (RobotServer)")
    parser.add_argument("--robot-port", type=int, default=5555)
    parser.add_argument("--gripper-host", default=None,
                        help="Gripper server host (default: same as --robot-ip)")
    parser.add_argument("--gripper-port", type=int, default=5556)
    parser.add_argument("--no-gripper", action="store_true",
                        help="Run without a gripper")
    parser.add_argument("--gripper-mode", default="binary", choices=["binary", "continuous"])
    parser.add_argument("--grasp-force", type=float, default=40.0)

    # ── Policy ───────────────────────────────────────────────────
    parser.add_argument("--policy-host", required=True, help="Policy server host (openpi)")
    parser.add_argument("--policy-port", type=int, default=8000)
    parser.add_argument("--prompt", default="manipulation", help="Language instruction")
    parser.add_argument("--replan-every", type=int, default=0,
                        help="Re-infer after this many steps of each chunk (0 = full chunk)")
    parser.add_argument("--action-scale", type=float, default=1.0,
                        help="Multiplier applied to policy actions before env.step")
    parser.add_argument("--policy-connect-timeout", type=float, default=30.0,
                        help="Seconds to wait for the policy server on startup")
    parser.add_argument("--infer-retry-timeout", type=float, default=120.0,
                        help="Reconnect+retry budget for failed inference (0 = fail fast)")

    # ── Control loop ─────────────────────────────────────────────
    parser.add_argument("--control-mode", default="ee_delta",
                        choices=["joint_abs", "joint_delta", "ee_abs", "ee_delta"])
    parser.add_argument("--fps", type=int, default=30, help="Control loop frequency")
    parser.add_argument("--max-steps", type=int, default=0, help="Stop after N steps (0 = no limit)")
    parser.add_argument("--duration", type=float, default=0.0,
                        help="Stop after N seconds (0 = until Ctrl+C)")

    # ── Cameras ──────────────────────────────────────────────────
    parser.add_argument("--cameras", default="config/cameras.yaml",
                        help="RealSense YAML config (default: config/cameras.yaml)")
    parser.add_argument("--mock-cameras", default=None,
                        help='Mock cameras, e.g. "front=synthetic,wrist=dir:/tmp/frames"')
    parser.add_argument("--no-camera", action="store_true", help="Disable cameras")
    parser.add_argument("--front-camera", default=None,
                        help="Camera name for observation/image (default: first)")
    parser.add_argument("--wrist-camera", default=None,
                        help="Camera name for observation/wrist_image (default: second)")
    parser.add_argument("--image-size", type=int, default=224,
                        help="Resize frames to SxS before sending (0 = keep native)")
    parser.add_argument("--display", default="auto", choices=["auto", "on", "off"])

    # ── Logging ──────────────────────────────────────────────────
    parser.add_argument("--log-jsonl", default=None,
                        help="Write per-step JSONL (timing + applied actions)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    return parser.parse_args()


def main():
    args = _parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        force=True,
    )

    cameras = _pick_cameras(args)
    front_name, wrist_name = _resolve_camera_names(
        cameras, args.front_camera, args.wrist_camera
    )
    gripper_host = None if args.no_gripper else (args.gripper_host or args.robot_ip)

    env = FrankaEnv(
        robot_ip=args.robot_ip,
        robot_port=args.robot_port,
        gripper_host=gripper_host,
        gripper_port=args.gripper_port,
        action_mode=args.control_mode,
        gripper_mode=args.gripper_mode,
        grasp_force=args.grasp_force,
    )
    display = Display(args.display)
    log_file = open(args.log_jsonl, "w") if args.log_jsonl else None

    running = True

    def _signal_handler(sig, frame):
        nonlocal running
        running = False
        logger.info("Shutting down ...")

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    logger.info(
        "Config: mode=%s, fps=%d, gripper=%s(%s), cameras=%s, image_size=%d, "
        "replan_every=%s, policy=%s:%d, prompt=%r",
        args.control_mode, args.fps, "off" if gripper_host is None else "on",
        args.gripper_mode, "off" if cameras is None else cameras.camera_names,
        args.image_size, args.replan_every or "chunk", args.policy_host,
        args.policy_port, args.prompt,
    )

    try:
        logger.info("Connecting to robot at %s:%d ...", args.robot_ip, args.robot_port)
        env.connect()
        logger.info("Resetting to home position ...")
        env.reset()

        action_dim = int(env.action_space.shape[0])
        logger.info("Connecting to policy server at %s:%d ...",
                    args.policy_host, args.policy_port)
        policy = ResilientPolicyClient(
            host=args.policy_host,
            port=args.policy_port,
            connect_timeout=args.policy_connect_timeout,
            retry_timeout=args.infer_retry_timeout,
        )
        metadata = policy.connect()
        logger.info("Policy metadata: %s", metadata)
        if "action_dim" in metadata and int(metadata["action_dim"]) != action_dim:
            logger.warning(
                "Policy metadata says action_dim=%s but the env action space is %dD",
                metadata["action_dim"], action_dim,
            )

        dt = 1.0 / args.fps
        chunk: deque = deque()
        last_images: dict = {}

        def build_obs() -> dict:
            """Fresh observation for each inference attempt (incl. retries)."""
            fresh = cameras.read_latest() if cameras is not None else {}
            return _build_policy_obs(
                env, fresh, front_name, wrist_name, args.image_size, args.prompt
            )

        stats = {
            "steps": 0, "infers": 0,
            "infer_ms": [], "rtt_ms": [], "loop_ms": [],
        }
        start_time = time.perf_counter()

        while running:
            loop_start = time.perf_counter()
            if args.max_steps and stats["steps"] >= args.max_steps:
                break
            if args.duration and loop_start - start_time >= args.duration:
                break

            frames = cameras.read_latest() if cameras is not None else {}
            for name, data in frames.items():
                if "rgb" in data:
                    last_images[name] = data["rgb"]

            infer_ms: Optional[float] = None
            rtt_ms: Optional[float] = None
            inferred = False
            if not chunk:
                infer_start = time.perf_counter()
                result = policy.infer(build_obs)
                rtt_ms = (time.perf_counter() - infer_start) * 1000.0

                actions = np.asarray(result.get("actions"), dtype=np.float32)
                if actions.ndim != 2 or actions.shape[1] != action_dim:
                    raise RuntimeError(
                        f"Policy returned actions with shape {actions.shape}; expected "
                        f"(H, {action_dim}). Check the policy's action dimension (env "
                        f"action space is {action_dim}D for '{args.control_mode}')."
                    )
                if args.action_scale != 1.0:
                    actions = actions * args.action_scale
                take = args.replan_every if args.replan_every > 0 else actions.shape[0]
                take = min(take, actions.shape[0])
                chunk.extend(actions[:take])

                server_ms = result.get("server_timing", {}).get("infer_ms")
                infer_ms = float(server_ms) if server_ms is not None else None
                inferred = True
                stats["infers"] += 1
                stats["rtt_ms"].append(rtt_ms)
                if infer_ms is not None:
                    stats["infer_ms"].append(infer_ms)
                logger.debug(
                    "infer #%d: %d/%d actions, server %.1f ms, rtt %.1f ms",
                    stats["infers"], take, actions.shape[0],
                    infer_ms if infer_ms is not None else float("nan"), rtt_ms,
                )

            action = chunk.popleft()
            obs_after, _, _, _, step_info = env.step(action)
            applied = np.asarray(step_info["applied_action"], dtype=np.float64)
            stats["steps"] += 1

            if display.enabled:
                work_elapsed = time.perf_counter() - loop_start
                display.show(
                    last_images,
                    f"DEPLOY - infer {stats['infers']}",
                    fps=1.0 / max(work_elapsed, 1e-9),
                    frame_count=stats["steps"],
                )

            # Pace the loop, then account for the full period (work + sleep),
            # so the reported rate and JSONL loop_ms show the real control rate.
            work_elapsed = time.perf_counter() - loop_start
            if work_elapsed < dt:
                time.sleep(dt - work_elapsed)
            elapsed = time.perf_counter() - loop_start
            stats["loop_ms"].append(elapsed * 1000.0)
            if log_file is not None:
                log_file.write(json.dumps({
                    "t": round(time.time(), 4),
                    "step": stats["steps"],
                    "loop_ms": round(elapsed * 1000.0, 2),
                    "inferred": inferred,
                    "infer_ms": None if infer_ms is None else round(infer_ms, 2),
                    "rtt_ms": None if rtt_ms is None else round(rtt_ms, 2),
                    "applied_action": np.round(applied, 6).tolist(),
                    "qpos": np.round(
                        np.asarray(obs_after["joint_pos"], dtype=np.float64), 6
                    ).tolist(),
                }) + "\n")
                log_file.flush()

            if stats["steps"] % args.fps == 0:
                logger.info(
                    "[%d steps] loop %.1f Hz | last rtt %s | infers: %d",
                    stats["steps"], 1.0 / max(elapsed, 1e-9),
                    "n/a" if rtt_ms is None else f"{rtt_ms:.1f} ms",
                    stats["infers"],
                )

        _log_summary(stats, args)

    finally:
        if log_file is not None:
            log_file.close()
        display.close()
        if cameras is not None:
            cameras.close()
        env.close()
        logger.info("Deploy session ended.")


def _log_summary(stats: dict, args) -> None:
    def _mean(values):
        return sum(values) / len(values) if values else float("nan")

    logger.info("=" * 50)
    logger.info(
        "Deploy summary: %d steps, %d infers (replan_every=%s)",
        stats["steps"], stats["infers"], args.replan_every or "chunk",
    )
    logger.info(
        "  loop:  mean %.1f Hz over %d steps",
        1000.0 / _mean(stats["loop_ms"]) if stats["loop_ms"] else float("nan"),
        len(stats["loop_ms"]),
    )
    if stats["infer_ms"]:
        logger.info("  server infer_ms: mean %.1f (max %.1f)",
                    _mean(stats["infer_ms"]), max(stats["infer_ms"]))
    if stats["rtt_ms"]:
        logger.info("  client rtt_ms:  mean %.1f (max %.1f)",
                    _mean(stats["rtt_ms"]), max(stats["rtt_ms"]))


if __name__ == "__main__":
    main()
