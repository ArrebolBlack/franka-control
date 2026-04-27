# Quick Start

This guide is the shortest path from a fresh checkout to moving the robot and
collecting a small dataset.

## 1. Machines and IPs

Use two machines when possible:

| Machine | Runs | Needs Franka FCI libraries |
|---|---|---|
| Control PC | `RobotServer`, `GripperServer` | Yes |
| Algorithm PC | teleop, planning, cameras, dataset collection | No |

Example addresses:

- Franka FCI IP: `192.168.0.2`
- Control PC IP: `192.168.0.100`
- Algorithm PC IP: `192.168.0.200`

## 2. Install

Algorithm PC:

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control
conda create -n franka python=3.12 -y
conda activate franka
python -m pip install -U pip setuptools wheel
python -m pip install -e ".[dev]"
```

Use the default `opencv-python` dependency if you need camera preview windows,
keyboard teleoperation focus behavior, or `scripts/play_dataset.py`. In a purely
headless environment, run collection with `--display off`.

Control PC:

```bash
git clone https://github.com/ArrebolBlack/franka-control.git
cd franka-control
conda create -n franka python=3.12 -y
conda activate franka
python -m pip install -U pip setuptools wheel
python -m pip install -e .
python -m pip install -e ".[control-machine]"
```

If your Franka FCI Python bindings are not available from pip, install
`aiofranka` and `pylibfranka` using your local Franka setup procedure.

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

## 3. Start Services

Control PC terminal 1:

```bash
python -m franka_control.robot \
    --fci-ip 192.168.0.2 \
    --port 5555 \
    --state-stream-port 5557
```

Control PC terminal 2:

```bash
python -m franka_control.gripper \
    --robot-ip 192.168.0.2 \
    --port 5556
```

## 4. Verify from Algorithm PC

```bash
python -m franka_control.scripts.measure_latency \
    --robot-ip 192.168.0.100 \
    -n 100
```

## 5. Teleoperate

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device spacemouse \
    --action-scale-t 1.0 \
    --action-scale-r 2.5
```

Keyboard fallback:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --device keyboard
```

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

## 6. Collect a Test Dataset

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/franka_demo \
    --root data/franka_demo \
    --task-name "test teleoperation" \
    --device keyboard \
    --control-mode ee_delta \
    --fps 30 \
    --num-episodes 3 \
    --display auto
```

No camera:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --repo-id test/state_only \
    --root data/state_only \
    --task-name "state only test" \
    --no-camera \
    --display off
```

## 7. Play Back

```bash
python scripts/play_dataset.py \
    --repo-id test/franka_demo \
    --root data/franka_demo
```
