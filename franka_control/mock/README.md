# Mock stack — run the pipeline without hardware

Stage-1 dry run: the robot is an aiofranka MuJoCo simulation, the gripper is a
simulated Franka Hand, cameras can be synthetic or image directories, and the
"cloud GPU" is a local mock policy server speaking the openpi websocket
protocol. `deploy_policy.py` talks to all of them through the exact same code
paths it will use on real hardware — moving to the real robot is a matter of
changing `--robot-ip`, `--gripper-host` and `--policy-host`.

## Runbook

Terminal 1 — mock control machine (robot on 5555/5557, gripper on 5556):

```bash
python -m franka_control.mock.launch            # add --viewer to watch the sim
```

Terminal 2 — mock "cloud" policy server (start this before the deploy script —
the openpi client waits silently if the server is absent):

```bash
python -m franka_control.mock.policy_server --port 8000 --delay-ms 0
```

Terminal 3 — deploy:

```bash
python -m franka_control.scripts.deploy_policy \
    --robot-ip 127.0.0.1 --gripper-host 127.0.0.1 \
    --policy-host 127.0.0.1 --prompt "pick cube" \
    --mock-cameras front=synthetic,wrist=synthetic \
    --fps 30 --duration 60 --log-jsonl /tmp/stage1.jsonl
```

The arm traces a small circle (the mock policy's scripted motion) and the
gripper toggles open/closed. Check `/tmp/stage1.jsonl` for per-step
`infer_ms` / `rtt_ms` / loop timing.

## Acceptance checks

```bash
# The repo's own scripts speak to the mock unchanged:
python -m franka_control.scripts.measure_latency --robot-ip 127.0.0.1 -n 100
python -m franka_control.scripts.teleop --robot-ip 127.0.0.1 --gripper-host 127.0.0.1 \
    --device keyboard --action-scale-t 0.5 --action-scale-r 1.0 --hz 50   # drives the sim

# Latency pressure test (simulates a slow cloud GPU):
python -m franka_control.mock.policy_server --port 8000 --delay-ms 300
python -m franka_control.scripts.deploy_policy ... --replan-every 8
```

## Notes

- **Keyboard teleop needs X11.** `--device keyboard` uses pynput, whose Linux
  backend is X11-only. On a Wayland session (e.g. default Ubuntu GNOME), a
  Wayland-native terminal's keystrokes never reach it — the arm simply will
  not move. Run the rehearsal terminal as an X11 client
  (`GDK_BACKEND=x11 gnome-terminal`), log into an "Ubuntu on Xorg" session,
  or use `--device spacemouse` (HID-based, unaffected).
- Individual servers can also run standalone:
  `python -m franka_control.mock.robot_server` / `...gripper_server`.
- `--object-width 0.03` (launch) makes `grasp()` stop on an object and return
  False, exercising the "blocking grasp while holding an object" path.
- `--fail-every N` (policy server) injects a traceback error frame.
- Ports 5555/5556/5557 are checked up front by the launcher; a real server on
  the same machine fails loudly instead of mixing with the mock.
- Expected noise: the sim prints a Ruckig progress bar during `move()` and
  nanobind leak reports when the interpreter exits — both harmless.
- Real cloud GPU (AutoDL) instead of the mock policy server: see
  `docs/cloud_gpu.md` (`scripts/cloud_tunnel.sh up` + `--policy-host 127.0.0.1`).
