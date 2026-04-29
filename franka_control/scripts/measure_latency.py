"""Measure ZMQ latency between algorithm machine and RobotServer.

Run on algorithm machine while RobotServer is running on control machine:
    python -m franka_control.scripts.measure_latency --robot-ip <CONTROL_IP>
    python -m franka_control.scripts.measure_latency --robot-ip <IP> -n 200
"""

import argparse
import statistics
import time

import msgpack
import numpy as np
import zmq


def main():
    parser = argparse.ArgumentParser(
        description="Measure ZMQ latency for teleop pipeline"
    )
    parser.add_argument("--robot-ip", required=True, help="Control machine IP")
    parser.add_argument("--port", type=int, default=5555)
    parser.add_argument(
        "-n", "--iterations", type=int, default=100,
        help="Iterations per test (default: 100)",
    )
    args = parser.parse_args()

    # ── Connect ────────────────────────────────────────────────────
    ctx = zmq.Context()
    sock = ctx.socket(zmq.DEALER)
    sock.setsockopt(zmq.RCVTIMEO, 5000)
    sock.setsockopt(zmq.SNDTIMEO, 5000)
    sock.connect(f"tcp://{args.robot_ip}:{args.port}")
    print(f"Connected to {args.robot_ip}:{args.port}\n")

    def rpc(command: str, params: dict = None) -> dict:
        """Send command and wait for reply (blocking)."""
        msg = {"command": command}
        if params:
            msg["params"] = params
        sock.send_multipart([b"", msgpack.packb(msg, use_bin_type=True)])
        parts = sock.recv_multipart()
        return msgpack.unpackb(parts[-1], raw=False)

    def send_only(command: str, params: dict = None) -> None:
        """Send command without waiting for reply (fire-and-forget)."""
        msg = {"command": command}
        if params:
            msg["params"] = params
        sock.send_multipart([b"", msgpack.packb(msg, use_bin_type=True)])

    def stats(label: str, times_ms: list[float]) -> None:
        s = sorted(times_ms)
        n = len(s)
        print(f"  [{label}]  n={n}")
        print(
            f"    min={s[0]:.2f}  max={s[-1]:.2f}  "
            f"mean={statistics.mean(s):.2f}  "
            f"median={statistics.median(s):.2f}  "
            f"p95={s[int(n * 0.95)]:.2f}  "
            f"p99={s[int(n * 0.99)]:.2f}  ms"
        )

    N = args.iterations
    ee = np.eye(4, dtype=np.float64)
    ee_bytes = ee.tobytes()
    ee_shape = [4, 4]

    # ── Test 1: get_state RTT (main thread, no controller thread) ──
    print("=== Test 1: get_state RTT (main thread only) ===")
    resp = rpc("get_state")
    connected = resp.get("state", {}).get("worker_status") is not None
    print(f"  Robot connected: {connected}")
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        rpc("get_state")
        times.append((time.perf_counter() - t0) * 1000)
    stats("get_state", times)

    # ── Test 2: set() send latency (fire-and-forget, no reply) ──
    print("\n=== Test 2: set(ee_desired) send latency (fire-and-forget) ===")
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        send_only("set", {
            "attr": "ee_desired", "value": ee_bytes, "shape": ee_shape,
        })
        times.append((time.perf_counter() - t0) * 1000)
    stats("set send", times)

    # ── Test 3: set() + get_state() serial (simulates step()) ──────
    print("\n=== Test 3: set() + get_state() serial (= one step()) ===")
    times = []
    for _ in range(N):
        t0 = time.perf_counter()
        send_only("set", {
            "attr": "ee_desired", "value": ee_bytes, "shape": ee_shape,
        })
        rpc("get_state")
        times.append((time.perf_counter() - t0) * 1000)
    stats("step()", times)

    # ── Test 4: Sustained send throughput ────────────────────────────
    print("\n=== Test 4: Sustained send throughput (3 seconds) ===")
    count = 0
    t_end = time.time() + 3.0
    while time.time() < t_end:
        send_only("set", {
            "attr": "ee_desired", "value": ee_bytes, "shape": ee_shape,
        })
        count += 1
    print(f"  {count} sends in 3s = {count / 3:.0f} Hz")

    # ── Test 5: Simulated 10Hz teleop loop (5 seconds) ────────────
    print("\n=== Test 5: Simulated 10Hz teleop loop (5 seconds) ===")
    dt = 0.1
    n_steps = 50
    step_durations = []
    t_loop_start = time.perf_counter()
    for _ in range(n_steps):
        t0 = time.perf_counter()
        send_only("set", {
            "attr": "ee_desired", "value": ee_bytes, "shape": ee_shape,
        })
        rpc("get_state")
        step_durations.append((time.perf_counter() - t0) * 1000)
        elapsed = time.perf_counter() - t0
        if elapsed < dt:
            time.sleep(dt - elapsed)
    total = time.perf_counter() - t_loop_start
    print(f"  Target: 10Hz | Actual: {n_steps / total:.1f}Hz | "
          f"Wall: {total:.2f}s")
    stats("step() in loop", step_durations)

    # ── Test 6: get_state() sustained throughput ──────────────────
    print("\n=== Test 6: get_state() sustained throughput (3 seconds) ===")
    count = 0
    t_end = time.time() + 3.0
    while time.time() < t_end:
        rpc("get_state")
        count += 1
    print(f"  {count} get_state in 3s = {count / 3:.0f} Hz")

    # ── Cleanup ────────────────────────────────────────────────────
    sock.close()
    ctx.term()
    print("\nDone.")


if __name__ == "__main__":
    main()
