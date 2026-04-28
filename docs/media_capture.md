# Media Capture Runbook

Use this runbook to capture the final README media assets for `v0.1.0`.
Only capture real robot motion after the workspace is clear, emergency stop is
reachable, and the first motion is low-speed.

## Required Assets

| Asset | Source workflow | Status |
|---|---|---|
| `docs/assets/system-architecture.png` | Generated architecture diagram | Complete |
| `docs/assets/teleop-preview.gif` | Keyboard or SpaceMouse teleoperation | Pending real capture |
| `docs/assets/data-collection-preview.gif` | Live collection preview with RealSense | Pending real capture |
| `docs/assets/dataset-player.png` | `scripts/play_dataset.py` playback window | Pending real capture |
| `docs/assets/trajectory-analysis.png` | Dataset trajectory/action plot | Pending real capture |

## General Rules

- Keep GIFs short: 5-15 seconds.
- Use low-speed motion and a clear workspace.
- Avoid showing faces, lab whiteboards, private network details, or unrelated
  equipment labels.
- Prefer crop-to-window captures over full desktop captures.
- Use stable filenames exactly as listed above so README links stay simple.
- Review each asset before committing it.

## Teleop Preview GIF

Run a low-speed teleop session from the algorithm PC:

```bash
python -m franka_control.scripts.teleop \
    --robot-ip 192.168.0.100 \
    --gripper-host 192.168.0.100 \
    --device keyboard \
    --action-scale-t 0.5 \
    --action-scale-r 1.0 \
    --hz 50
```

Capture a short clip showing controlled, low-speed end-effector motion. Save it
as:

```text
docs/assets/teleop-preview.gif
```

Acceptance:

- Motion direction is understandable.
- No unsafe or high-speed motion is shown.
- The robot and end-effector are visible.

## Data Collection Preview GIF

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
    --fps 30 \
    --num-episodes 1 \
    --cameras config/cameras.yaml \
    --display auto
```

Capture the OpenCV preview window during preview or recording. Save it as:

```text
docs/assets/data-collection-preview.gif
```

Acceptance:

- At least one camera feed is visible.
- The `PREVIEW` or `RECORDING` overlay is readable.
- The clip does not reveal sensitive lab context.

## Dataset Player Screenshot

Open the collected dataset:

```bash
python scripts/play_dataset.py \
    --repo-id test/franka_media \
    --root data/franka_media
```

Capture a screenshot of the player window and save it as:

```text
docs/assets/dataset-player.png
```

Acceptance:

- The HUD and camera layout are readable.
- The selected frame is representative and not blurred.

## Trajectory and Action Analysis Screenshot

In the dataset player, use the visualization controls:

- `v` for trajectory visualization.
- `a` for action distribution.
- `i` for action statistics in the terminal.

Capture either the trajectory visualization or action distribution figure and
save it as:

```text
docs/assets/trajectory-analysis.png
```

Acceptance:

- Axis labels and plotted data are readable.
- The plot corresponds to the same real validation dataset.

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
