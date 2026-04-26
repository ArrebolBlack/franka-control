"""Play a LeRobot dataset video with cv2.

Usage:
    python scripts/play_dataset.py --root /tmp/test_cameras --repo-id test/cameras
    python scripts/play_dataset.py --root /tmp/test_cameras --repo-id test/cameras --camera d405
"""

import argparse

import cv2
import numpy as np
from lerobot.datasets.lerobot_dataset import LeRobotDataset


def _to_display(img_tensor) -> np.ndarray:
    """Convert CHW float32 tensor to HWC uint8 BGR for cv2."""
    img = img_tensor.numpy() if hasattr(img_tensor, "numpy") else np.array(img_tensor)
    if img.ndim == 3 and img.shape[0] in (1, 3):
        img = np.transpose(img, (1, 2, 0))
    if img.dtype != np.uint8:
        img = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    return img[:, :, ::-1].copy()  # RGB -> BGR


def main():
    parser = argparse.ArgumentParser(description="Play LeRobot dataset video")
    parser.add_argument("--root", required=True)
    parser.add_argument("--repo-id", required=True)
    parser.add_argument("--episode", type=int, default=0)
    parser.add_argument("--camera", default=None, help="Single camera to show (e.g. d435). Default: all side-by-side")
    parser.add_argument("--fps", type=int, default=None, help="Playback fps (default: dataset fps)")
    args = parser.parse_args()

    ds = LeRobotDataset(args.repo_id, root=args.root)
    playback_fps = args.fps or ds.fps

    image_keys = [k for k in ds[0].keys() if k.startswith("observation.images.")]
    if not image_keys:
        print("No image keys found in dataset.")
        return

    if args.camera:
        cam_keys = [f"observation.images.{args.camera}"]
    else:
        cam_keys = image_keys

    for k in cam_keys:
        if k not in image_keys:
            print(f"Camera '{k}' not found. Available: {image_keys}")
            return

    ep_frames = [i for i in range(ds.num_frames) if ds[i]["episode_index"].item() == args.episode]
    if not ep_frames:
        print(f"Episode {args.episode} not found.")
        return

    print(f"Playing {cam_keys} | episode {args.episode} | {len(ep_frames)} frames @ {playback_fps}fps")
    print("Controls: Space=pause, Q=quit, Left/Right=seek")

    cv2.namedWindow("LeRobot Player", cv2.WINDOW_NORMAL)

    idx = 0
    paused = False

    while idx < len(ep_frames):
        sample = ds[ep_frames[idx]]

        # Build display: cameras side-by-side
        frames = []
        for k in cam_keys:
            frames.append(_to_display(sample[k]))

        # Resize to same height if needed, then hstack
        h = frames[0].shape[0]
        resized = []
        for f in frames:
            if f.shape[0] != h:
                w = int(f.shape[1] * h / f.shape[0])
                f = cv2.resize(f, (w, h))
            resized.append(f)
        display = np.hstack(resized)

        # Overlay info
        gw = sample["observation.state"].numpy()[-1]
        cv2.putText(display, f"Frame {idx}/{len(ep_frames)-1}  gripper={gw:.3f}",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        cv2.imshow("LeRobot Player", display)
        wait_ms = 0 if paused else max(1, int(1000 / playback_fps))
        key = cv2.waitKey(wait_ms) & 0xFF

        if key == ord('q') or key == 27:
            break
        elif key == ord(' '):
            paused = not paused
            continue
        elif key == 81 or key == 2:  # Left
            idx = max(0, idx - 1)
            continue
        elif key == 83 or key == 3:  # Right
            idx = min(len(ep_frames) - 1, idx + 1)
            continue

        if not paused:
            idx += 1

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
