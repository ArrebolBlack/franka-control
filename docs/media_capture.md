# Media Capture Runbook

Use this runbook to capture the final README media assets for `v0.1.0`.
Only capture real robot motion after the workspace is clear, emergency stop is
reachable, and the first motion is low-speed.

## Required Assets

| Asset | Source workflow | Status |
|---|---|---|
| `docs/assets/system-architecture.png` | Generated architecture diagram | Complete |
| `docs/assets/keyboard-teleop-install-gear.mp4` | Keyboard teleoperation, gear insertion task | Complete |
| `docs/assets/spacemouse-teleop-pouring.mp4` | SpaceMouse teleoperation, pouring task | Complete |
| `docs/assets/dataset-player-fruit-basket.mp4` | `scripts/play_dataset.py` playback of fruit basket task | Complete |
| `docs/assets/trajectory-analysis.png` | Dataset trajectory plot from player key `v` | Complete |
| `docs/assets/action-distribution.png` | Dataset action distribution plot from player key `a` | Complete |

Optional:

| Asset | Source workflow | Status |
|---|---|---|
| `docs/assets/data-collection-preview.gif` | Live OpenCV collection preview | Optional, not required for `v0.1.0` |

## General Rules

- Keep videos short and focused.
- Use low-speed motion and a clear workspace.
- Avoid showing faces, lab whiteboards, private network details, or unrelated
  equipment labels.
- Prefer crop-to-window captures over full desktop captures.
- Use stable filenames exactly as listed above so README links stay simple.
- Review each asset before committing it.

## Keyboard Teleoperation Video

Use the keyboard teleoperation gear insertion demo:

```text
docs/assets/keyboard-teleop-install-gear.mp4
```

Acceptance:

- The gear insertion task is visible.
- The clip demonstrates controlled, low-speed keyboard teleoperation.
- No unsafe or high-speed motion is shown.

Reference command:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

## SpaceMouse Teleoperation Video

Use the SpaceMouse pouring demo:

```text
docs/assets/spacemouse-teleop-pouring.mp4
```

Acceptance:

- The pouring task is visible.
- The clip demonstrates continuous 6-DoF SpaceMouse control.
- No unsafe or high-speed motion is shown.

Reference command:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --device spacemouse \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

## Dataset Playback Video

Use the dataset player recording:

```text
docs/assets/dataset-player-fruit-basket.mp4
```

Acceptance:

- The player output shows the fruit basket task.
- Camera views and playback HUD/text are readable enough to identify that the
  clip is post-collection dataset playback.
- The clip does not reveal sensitive lab context.

Reference command:

```bash
python scripts/play_dataset.py \
    --repo-id test/franka_media \
    --root data/franka_media
```

## Analysis Figures

The dataset player analysis controls produce:

```text
docs/assets/trajectory-analysis.png
docs/assets/action-distribution.png
```

Controls:

- `v` for trajectory visualization.
- `a` for action distribution.
- `i` for action statistics in the terminal.

Acceptance:

- Axis labels and plotted data are readable.
- The figures correspond to a real collected dataset.

## Optional Collection Preview

Run one short collection session with cameras:

```bash
python -m franka_control.scripts.collect_episodes \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --repo-id test/franka_media \
    --root data/franka_media \
    --task-name "media capture validation" \
    --device keyboard \
    --control-mode ee_delta \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --fps 30 \
    --num-episodes 1 \
    --cameras config/cameras.yaml \
    --display auto
```

Capture the OpenCV preview window during preview or recording only if a live
collection preview is needed. This asset is optional for `v0.1.0` because the
dataset playback video and hardware validation record already demonstrate
camera-backed collection.

```text
docs/assets/data-collection-preview.gif
```

Acceptance:

- At least one camera feed is visible.
- The `PREVIEW` or `RECORDING` overlay is readable.
- The clip does not reveal sensitive lab context.

## Recommended Final Check

After adding assets:

```bash
python scripts/check_markdown_links.py
git diff --check
python -m pytest tests -q
```

Then update:

- `README.md` media section if links change.
- `docs/assets/README.md` if asset names or formats change.
- `progress.md` and `todo.md` with the completed media items.
