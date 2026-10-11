"""Mock policy server speaking the openpi websocket protocol.

Stands in for the cloud GPU during hardware-free dry runs: ``deploy_policy.py``
talks to it through the very same ``openpi_client`` code path it will use
against the real ``openpi/scripts/serve_policy.py`` — only ``--policy-host``
changes later.

Wire protocol (mirrors openpi's serving/websocket_policy_server.py):
- on connect the server sends its metadata (msgpack-numpy) as the first frame
- per request: recv obs (msgpack-numpy dict) -> infer -> send
  ``{"actions": (H, D) array, "server_timing": {"infer_ms": ...}}``
- on error: send the traceback as a string, then close with code 1011

The default policy is open loop: ee-delta circles plus a squared gripper
channel, so binary gripper mode edge-triggers (like a real policy's command)
instead of ramping.

Usage:
    python -m franka_control.mock.policy_server --port 8000 --delay-ms 0
"""

from __future__ import annotations

import argparse
import asyncio
import http
import logging
import random
import time
import traceback

import numpy as np

try:
    import websockets.asyncio.server as _ws_server
    import websockets.frames
    from openpi_client import msgpack_numpy
except ImportError as _exc:  # pragma: no cover - reported in main()
    msgpack_numpy = None
    _IMPORT_ERROR = _exc
else:
    _IMPORT_ERROR = None

logger = logging.getLogger(__name__)


class MockPolicy:
    """Scripted policy: ee-delta circle with a squared gripper channel.

    Actions are open-loop (obs is ignored): ``[dx, dy, dz, drx, dry, drz,
    gripper, ...]`` where dx/dy trace a circle of per-step radius ``radius``
    and the gripper channel toggles between 0 and 1 every ``gripper_period``
    steps (binary-mode compatible).
    """

    def __init__(
        self,
        action_dim: int = 7,
        horizon: int = 16,
        period: float = 120.0,
        radius: float = 0.005,
        gripper_period: int = 120,
    ):
        self.action_dim = action_dim
        self.horizon = horizon
        self._period = max(float(period), 1.0)
        self._radius = float(radius)
        self._gripper_period = max(int(gripper_period), 1)
        self._step = 0

    def infer(self, obs) -> dict:
        actions = np.zeros((self.horizon, self.action_dim), dtype=np.float32)
        for k in range(self.horizon):
            phase = 2.0 * np.pi * (self._step + k) / self._period
            if self.action_dim >= 1:
                actions[k, 0] = self._radius * np.sin(phase)
            if self.action_dim >= 2:
                actions[k, 1] = self._radius * np.cos(phase)
        if self.action_dim >= 7:
            open_half = (self._step // self._gripper_period) % 2 == 0
            actions[:, 6] = 1.0 if open_half else 0.0
        self._step += self.horizon
        return {"actions": actions}


class MockPolicyServer:
    """openpi-protocol websocket server (see module docstring)."""

    def __init__(
        self,
        policy: MockPolicy,
        host: str = "0.0.0.0",
        port: int = 8000,
        metadata: dict | None = None,
        delay_ms: float = 0.0,
        jitter_ms: float = 0.0,
        fail_every: int = 0,
    ):
        self._policy = policy
        self._host = host
        self._port = port
        self._metadata = metadata or {}
        self._delay_ms = float(delay_ms)
        self._jitter_ms = float(jitter_ms)
        self._fail_every = int(fail_every)
        self._requests = 0

    def serve_forever(self) -> None:
        asyncio.run(self._run())

    async def _run(self) -> None:
        async with _ws_server.serve(
            self._handler,
            self._host,
            self._port,
            compression=None,
            max_size=None,  # images exceed websockets' 1 MB default
            process_request=_health_check,
        ) as server:
            logger.info("Mock policy server listening on %s:%d", self._host, self._port)
            await server.serve_forever()

    async def _handler(self, websocket):
        logger.info("Connection from %s opened", websocket.remote_address)
        packer = msgpack_numpy.Packer()
        await websocket.send(packer.pack(self._metadata))

        prev_total_time = None
        while True:
            try:
                start_time = time.monotonic()
                obs = msgpack_numpy.unpackb(await websocket.recv())
                infer_start = time.monotonic()

                self._requests += 1
                if self._fail_every and self._requests % self._fail_every == 0:
                    raise RuntimeError("mock failure injection (--fail-every)")
                if self._delay_ms > 0 or self._jitter_ms > 0:
                    await asyncio.sleep(
                        (self._delay_ms + random.uniform(0.0, self._jitter_ms)) / 1000.0
                    )
                action = self._policy.infer(obs)
                infer_ms = (time.monotonic() - infer_start) * 1000.0

                action["server_timing"] = {"infer_ms": infer_ms}
                if prev_total_time is not None:
                    # Mirror openpi: last request's total (recv->send) time.
                    action["server_timing"]["prev_total_ms"] = prev_total_time * 1000.0
                await websocket.send(packer.pack(action))
                prev_total_time = time.monotonic() - start_time
            except websockets.ConnectionClosed:
                logger.info("Connection from %s closed", websocket.remote_address)
                break
            except Exception:
                await websocket.send(traceback.format_exc())
                await websocket.close(
                    code=websockets.frames.CloseCode.INTERNAL_ERROR,
                    reason="Internal server error. Traceback included in previous frame.",
                )
                raise


def _health_check(connection, request):
    if request.path == "/healthz":
        return connection.respond(http.HTTPStatus.OK, "OK\n")
    return None


def main():
    parser = argparse.ArgumentParser(
        description="Mock policy server (openpi websocket protocol, no GPU)"
    )
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--action-dim", type=int, default=7,
                        help="Action dimension (7 = ee_delta [6] + gripper)")
    parser.add_argument("--horizon", type=int, default=16, help="Action chunk length")
    parser.add_argument("--radius", type=float, default=0.005,
                        help="EE circle radius per step [m]")
    parser.add_argument("--period", type=float, default=120.0,
                        help="Steps per circle revolution")
    parser.add_argument("--gripper-period", type=int, default=120,
                        help="Steps between gripper toggles")
    parser.add_argument("--delay-ms", type=float, default=0.0,
                        help="Simulated GPU inference latency")
    parser.add_argument("--jitter-ms", type=float, default=0.0,
                        help="Extra random latency [0, jitter) per request")
    parser.add_argument("--fail-every", type=int, default=0,
                        help="Fail every Nth request (0 = never)")
    parser.add_argument("--log-level", default="INFO",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    args = parser.parse_args()

    if msgpack_numpy is None:
        raise SystemExit(
            f"openpi_client is required ({_IMPORT_ERROR}). Install it with:\n"
            "  pip install --no-deps -e <openpi>/packages/openpi-client"
        )

    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    policy = MockPolicy(
        action_dim=args.action_dim,
        horizon=args.horizon,
        period=args.period,
        radius=args.radius,
        gripper_period=args.gripper_period,
    )
    metadata = {
        "policy": "mock-circle",
        "action_dim": args.action_dim,
        "action_horizon": args.horizon,
    }
    server = MockPolicyServer(
        policy,
        host=args.host,
        port=args.port,
        metadata=metadata,
        delay_ms=args.delay_ms,
        jitter_ms=args.jitter_ms,
        fail_every=args.fail_every,
    )
    server.serve_forever()


if __name__ == "__main__":
    main()
