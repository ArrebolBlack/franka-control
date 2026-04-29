# Media Assets

This directory stores project videos, screenshots, diagrams, and analysis figures
used by the README and documentation.

Release media:

| File | Description |
|---|---|
| `logo.png` | Franka Control project logo used at the top of the README |
| `system-architecture.png` | Full project architecture: dual-machine ZMQ control, data collection, trajectory, kinematics, playback, and analysis |
| `keyboard-teleop-install-gear.mp4` | Keyboard teleoperation on a gear insertion task |
| `keyboard-teleop-install-gear.gif` | Compressed GIF preview (480px, 10fps) for README inline loop |
| `spacemouse-teleop-pouring.mp4` | SpaceMouse teleoperation on a pouring task |
| `spacemouse-teleop-pouring.gif` | Compressed GIF preview (480px, 10fps) for README inline loop |
| `dataset-player-fruit-basket.mp4` | Dataset playback for the fruit basket task |
| `dataset-player-fruit-basket.gif` | Compressed GIF preview (480px, 10fps) for README inline loop |
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
