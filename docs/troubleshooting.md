# Troubleshooting

This page lists common setup and runtime failures for Franka Control. Commands
that can move hardware should only be retried after the robot workspace is clear,
the emergency stop is reachable, and the first motion is low-speed.

## Robot Server Connection Failures

Symptoms:

- `RobotClient` cannot connect to `tcp://<control-pc>:5555`.
- `python -m franka_control.robot` exits during startup.
- `measure_latency` times out on `get_state`.

Checks:

1. Run the robot server on the control PC, not on the algorithm PC:

```bash
python -m franka_control.robot \
    --fci-ip 192.168.0.2 \
    --port 5555 \
    --state-stream-port 5557 \
    --poll-hz 1000
```

2. Verify the algorithm PC can reach the control PC:

```bash
ping 192.168.0.100
nc -vz 192.168.0.100 5555
nc -vz 192.168.0.100 5557
```

3. On the control PC, verify the Franka FCI address is reachable:

```bash
ping 192.168.0.2
```

4. Confirm `aiofranka` is installed in the control-machine environment.

Expected result:

- `RobotServer` logs that it is listening on port `5555`.
- `measure_latency` can connect to `192.168.0.100:5555`.

## `--fci-ip` vs `--robot-ip` Mistakes

These two addresses are different in a dual-machine setup.

| Argument | Used on | Meaning |
|---|---|---|
| `--fci-ip` | Control PC | Franka robot FCI address, for example `192.168.0.2` |
| `--robot-ip` | Algorithm PC scripts | Control PC address, for example `192.168.0.100` |
| `--gripper-host` | Algorithm PC scripts | Gripper service host, usually the control PC address |

Correct pattern:

```bash
# Control PC
python -m franka_control.robot --fci-ip 192.168.0.2

# Algorithm PC
python -m franka_control.scripts.measure_latency --robot-ip 192.168.0.100
```

Common error:

```bash
# Wrong for algorithm-side scripts unless the control PC is also 192.168.0.2.
python -m franka_control.scripts.teleop --robot-ip 192.168.0.2
```

## ZMQ Port Conflicts

Default ports:

| Service | Default port |
|---|---:|
| Robot RPC | `5555` |
| Gripper RPC | `5556` |
| Robot state stream | `5557` |

Check listeners on the control PC:

```bash
ss -ltnp | grep -E '5555|5556|5557'
```

If another process owns a port, stop it or choose explicit ports:

```bash
python -m franka_control.robot \
    --fci-ip 192.168.0.2 \
    --port 5565 \
    --state-stream-port 5567
```

Then pass the matching client-side port if the script exposes one. Keep robot,
gripper, and state-stream ports distinct.

## Gripper Service Failures

Symptoms:

- `GripperServer` exits with `pylibfranka is not installed`.
- Gripper commands time out or return busy.
- Robot motion works but open/close commands do nothing.

Checks:

1. Run the gripper service on the control PC:

```bash
python -m franka_control.gripper \
    --robot-ip 192.168.0.2 \
    --port 5556 \
    --poll-hz 50
```

2. Confirm the algorithm-side scripts point to the control PC:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --device keyboard
```

3. If the gripper remains busy, stop the command, restart `GripperServer`, and
   retry with a clear object-free gripper workspace.

Notes:

- `--robot-ip` on `GripperServer` means the Franka robot IP.
- `--gripper-host` on algorithm scripts means the control PC host.

## RealSense Device Not Found

Symptoms:

- `CameraManager.from_yaml` fails.
- Collection starts only with `--no-camera`.
- A configured serial number is not detected.

Checks:

```bash
rs-enumerate-devices
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/camera_check \
    --root data/camera_check \
    --task-name "camera check" \
    --num-episodes 1 \
    --cameras config/cameras.yaml \
    --display auto
```

Fixes:

- Update `config/cameras.yaml` with the actual serial numbers.
- Use a powered USB hub or direct USB3 port.
- Reduce camera FPS or resolution if frames drop.
- Use `--no-camera --display off` to isolate robot/data path issues.

## SpaceMouse Permission Problems

Symptoms:

- SpaceMouse is not detected.
- Teleop starts, but no SpaceMouse motion appears.
- HID access errors appear on Linux.

Install HID libraries and udev rules:

```bash
sudo apt install libhidapi-hidraw0 libhidapi-libusb0
sudo tee /etc/udev/rules.d/99-spacemouse.rules > /dev/null <<'RULES'
SUBSYSTEM=="usb", ATTRS{idVendor}=="256f", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="256f", MODE="0666"
RULES
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Then unplug and reconnect the device. If SpaceMouse remains unavailable, verify
the rest of the stack with keyboard teleop:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0
```

## Keyboard Focus and Terminal Input Problems

Symptoms:

- Keyboard teleop does not move the robot.
- `Esc`, `s`, or episode commands are ignored.
- Commands work only when the wrong window is focused.

Checks:

- Run keyboard teleop from a local desktop terminal, not a detached background
  shell.
- Keep focus on the terminal or OpenCV preview window, depending on the command.
- Avoid terminal multiplexers until the basic path is working.
- Use conservative scales during diagnosis:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

## OpenCV GUI vs Headless Environment Problems

Symptoms:

- `cv2.imshow` crashes or hangs.
- Dataset player does not open a window.
- Collection logs that `DISPLAY` or `WAYLAND_DISPLAY` is missing.

Options:

- On a desktop algorithm PC, keep `opencv-python` installed and run with:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/gui \
    --root data/gui \
    --display auto
```

- On a headless machine, disable preview:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/headless \
    --root data/headless \
    --no-camera \
    --display off
```

- Do not install `opencv-python-headless` if you need `scripts/play_dataset.py`
  or live preview windows.

## LeRobot Dataset Creation or Resume Errors

Symptoms:

- `DataCollector` fails during dataset creation.
- `--resume` rejects an existing directory.
- Playback cannot find episodes or frames.

Checks:

1. Use a fresh local root for a minimal state-only test:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/state_only \
    --root data/state_only \
    --task-name "state only test" \
    --device keyboard \
    --control-mode ee_delta \
    --fps 30 \
    --num-episodes 1 \
    --no-camera \
    --display off
```

2. Resume only when the command uses the same schema and control mode:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/state_only \
    --root data/state_only \
    --task-name "state only test" \
    --control-mode ee_delta \
    --resume
```

3. Inspect with the player on a GUI-capable machine:

```bash
python scripts/play_dataset.py \
    --repo-id test/state_only \
    --root data/state_only
```

## Unsafe or Unexpected Robot Motion Checklist

Stop the session immediately if motion is larger, faster, or in a different
direction than expected.

Before retrying:

- Clear the workspace and keep the emergency stop reachable.
- Reduce `--action-scale-t`, `--action-scale-r`, `--vel-scale`, and
  `--acc-scale`.
- Confirm the selected control mode matches the command shape:
  `ee_delta`, `ee_abs`, `joint_delta`, or `joint_abs`.
- Confirm units:
  - Cartesian translation is meters.
  - Rotation-vector values are radians.
  - Joint angles are radians.
  - Gripper width is meters.
- Verify `--robot-ip` points to the intended control PC.
- Run a dry trajectory plan before execution:

```bash
python -m franka_control.scripts.run_trajectory \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --vel-scale 0.2 \
    --acc-scale 0.2 \
    --dry-run
```

- For hardware execution, start with a slow route:

```bash
python -m franka_control.scripts.run_trajectory \
    --robot-ip 192.168.0.100 \
    --waypoints config/waypoints.yaml \
    --route pick_place \
    --vel-scale 0.2 \
    --acc-scale 0.2 \
    --time-scale 3.0
```

If unexpected motion is reproducible, record the exact command, logs, robot
state, and whether emergency stop was required before opening a hardware issue.
