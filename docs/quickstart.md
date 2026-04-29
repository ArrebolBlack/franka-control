# Quick Start

This guide takes a new user from a fresh checkout to a first low-speed test.
Follow the paths in order. Path A is offline and safe to run without a robot.
Paths B and C can connect to and move real hardware.

## Machines and IPs

Use two machines when possible:

| Machine | Runs | Needs Franka FCI libraries |
|---|---|---|
| Control PC | `RobotServer`, `GripperServer` | Yes |
| Algorithm PC | teleop, planning, cameras, dataset collection | No |

Example addresses used below:

| Name | Example | Meaning |
|---|---|---|
| Franka FCI IP / `--fci-ip` | `192.168.0.2` | Robot FCI address, used by `RobotServer` on the control PC |
| Control PC IP / `--robot-ip` | `192.168.0.100` | Control PC address, used by algorithm-side scripts |
| Algorithm PC IP | `192.168.0.200` | Machine running teleop, cameras, and dataset tools |
| `--gripper-host` | `192.168.0.100` | Gripper service host, usually the same as `--robot-ip` |

Do not pass the Franka FCI IP as `--robot-ip` on the algorithm PC unless the
control service is actually running on that same address.

## Path A: Offline Inspection, No Robot Required

Run on either machine.

Install:

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control
conda create -n franka python=3.12 -y
conda activate franka
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

Expected output:

- `pip install` finishes without hardware access.
- The package is importable from the checkout.

Run offline checks:

```bash
python -m pytest tests -q
python -m py_compile \
    franka_control/scripts/collect_episodes.py \
    franka_control/scripts/teleop.py \
    franka_control/scripts/run_trajectory.py \
    scripts/play_dataset.py
python scripts/check_markdown_links.py
```

Expected output:

- Unit tests pass.
- `py_compile` prints no output on success.
- Markdown link check prints `Markdown link check passed.`

CLI help smoke tests:

```bash
python -m franka_control.robot --help
python -m franka_control.gripper --help
python -m franka_control.scripts.teleop --help
python -m franka_control.scripts.collect_episodes --help
python -m franka_control.scripts.collect_waypoints --help
python -m franka_control.scripts.run_trajectory --help
python -m franka_control.scripts.measure_latency --help
python scripts/play_dataset.py --help
```

Expected output:

- Each command prints usage text.
- None of these `--help` commands should connect to hardware.

## Path B: Control PC Services

Run this path on the control PC connected to Franka FCI.

Install control-machine dependencies:

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control
conda create -n franka python=3.12 -y
conda activate franka
python -m pip install -U pip setuptools wheel
python -m pip install -e .
python -m pip install -e ".[control-machine]"
```

If `aiofranka` or `pylibfranka` cannot be installed from pip in your lab setup,
install them using your local Franka FCI procedure.

Safety check before starting services:

- The robot workspace is clear.
- The robot is in an expected Franka Desk state for FCI control.
- Emergency stop is reachable.
- The control PC can reach the Franka FCI IP.

Start `RobotServer` on the control PC:

```bash
python -m franka_control.robot \
    --fci-ip 192.168.0.2 \
    --port 5555 \
    --state-stream-port 5557 \
    --poll-hz 1000
```

Expected output:

- Logs show `Robot server listening on port 5555`.
- The process remains running.

Start `GripperServer` on the control PC in a second terminal:

```bash
python -m franka_control.gripper \
    --robot-ip 192.168.0.2 \
    --port 5556 \
    --poll-hz 50
```

Expected output:

- Logs show the gripper connected.
- Logs show `Gripper server listening on port 5556`.

## Path C: Algorithm PC Teleop and Data Collection

Run this path on the algorithm/GPU PC. Keep the control PC services from Path B
running.

Install algorithm-machine dependencies:

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control
conda create -n franka python=3.12 -y
conda activate franka
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

For SpaceMouse access on Linux:

```bash
sudo apt install libhidapi-hidraw0 libhidapi-libusb0
sudo tee /etc/udev/rules.d/99-spacemouse.rules > /dev/null <<'RULES'
SUBSYSTEM=="usb", ATTRS{idVendor}=="256f", MODE="0666"
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="256f", MODE="0666"
RULES
sudo udevadm control --reload-rules
sudo udevadm trigger
```

Measure latency from the algorithm PC:

```bash
python -m franka_control.scripts.measure_latency \
    --robot-ip 192.168.0.100 \
    -n 100
```

Expected output:

- The command connects to `192.168.0.100:5555`.
- It prints latency statistics for `get_state`, `set ee_desired`, and simulated
  step timing.

Safety warning before teleoperation:

- This command can move the real robot.
- Use low speed first.
- Keep one hand near emergency stop.
- Stop immediately if motion direction or scale is unexpected.

Run low-speed keyboard teleop:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

Expected output:

- Logs show the script connected to the robot.
- Keyboard controls are printed.
- Small key presses produce small robot motion.

Keyboard controls:

| Key | Action |
|---|---|
| `W/S` | +/- X |
| `A/D` | +/- Y |
| `R/F` | +/- Z |
| `Q/E` | +/- yaw |
| `Z/X` | +/- pitch |
| `C/V` | +/- roll |
| `Space` | close gripper |
| `Enter` | open gripper |
| `Shift` | slow mode |
| `Esc` | exit |

Safety warning before SpaceMouse teleoperation:

- SpaceMouse axes can feel sensitive on first use.
- Keep the same low speeds until axis directions are confirmed.

Run low-speed SpaceMouse teleop:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --device spacemouse \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

Expected output:

- Logs show SpaceMouse is ready.
- Left and right buttons command the gripper when the gripper service is running.

Safety warning before data collection:

- The preview phase still moves the robot.
- Start with one short state-only episode before enabling cameras.

Collect one state-only test episode:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --repo-id test/state_only \
    --root data/state_only \
    --task-name "state only validation" \
    --device keyboard \
    --control-mode ee_delta \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --fps 30 \
    --num-episodes 1 \
    --no-camera \
    --display off
```

Expected output:

- The script enters preview mode.
- Press `s` to start recording.
- Press `Esc` to end the episode.
- Press `Y` or `N` when asked for success/failure.
- The dataset is written under `data/state_only`.

Collect one camera test episode:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --repo-id test/franka_demo \
    --root data/franka_demo \
    --task-name "test teleoperation" \
    --device keyboard \
    --control-mode ee_delta \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --fps 30 \
    --num-episodes 1 \
    --cameras config/cameras.yaml \
    --display auto
```

Expected output:

- The configured camera names are logged.
- A preview window opens if OpenCV GUI support is available.
- Recorded frames include robot state, action, task text, and RGB images.
- If the dataset root already exists, use `--resume` or a fresh `--repo-id` /
  `--root`; failing without `--resume` is expected.

Play back the dataset on a GUI-capable machine:

```bash
python scripts/play_dataset.py \
    --repo-id test/franka_demo \
    --root data/franka_demo
```

Expected output:

- The player reports the number of episodes and frames.
- An OpenCV window shows dataset playback.

## Next Steps

- Read [Troubleshooting](troubleshooting.md) if any command above fails.
- Record tested setup details in [Hardware Validation](hardware_validation.md).
- Read [Data Collection](data_collection.md) for resume, annotation, and player
  details.
