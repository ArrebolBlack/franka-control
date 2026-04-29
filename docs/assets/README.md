# Media Assets

This directory stores project videos, screenshots, diagrams, and analysis figures
used by the README and documentation.

Release media:

| File | Description |
|---|---|
| `system-architecture.png` | Dual-machine ZMQ architecture |
| `keyboard-teleop-install-gear.mp4` | Keyboard teleoperation on a gear insertion task |
| `spacemouse-teleop-pouring.mp4` | SpaceMouse teleoperation on a pouring task |
| `dataset-player-fruit-basket.mp4` | Dataset playback for the fruit basket task |
| `trajectory-analysis.png` | Dataset trajectory visualization from the `v` player action |
| `action-distribution.png` | Dataset action distribution from the `a` player action |

Keep binary assets small enough for GitHub. Prefer compressed PNG and short MP4
clips only when they materially improve the documentation. A live
`data-collection-preview` clip is optional for `v0.1.0`; the saved dataset
playback video and hardware validation record already demonstrate camera-backed
collection.

For the capture workflow and safety checklist, see
[Media Capture Runbook](../media_capture.md). For the full list of required
hardware information, validation evidence, media, and release inputs, see
[Release Materials Checklist](../release_materials_checklist.md).
