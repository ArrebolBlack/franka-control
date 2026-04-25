# Real Robot Test Plan - Data Collection System

## Prerequisites
- Control machine: RobotServer running on port 5555
- Control machine: GripperServer running on port 5556
- Algorithm machine: All dependencies installed (lerobot, pyrealsense2, pyspacemouse/pynput)
- Robot: Unlocked and FCI enabled
- Cameras: RealSense cameras connected (optional for some tests)

## Test 1: State Streaming During Blocking Operations
**Purpose:** Verify RobotServer streams state continuously during move_to()

**Steps:**
1. Start RobotServer on control machine
2. Run: `python -m franka_control.scripts.measure_latency --robot-ip <CONTROL_IP>`
3. During latency measurement, trigger a blocking move_to() from another terminal:
   ```python
   from franka_control.envs import FrankaEnv
   import numpy as np
   env = FrankaEnv(robot_ip="<CONTROL_IP>", action_mode="joint_abs")
   env.reset()
   target = np.array([0.1, -0.8, 0.1, -2.3, 0.1, 1.6, 0.8])
   env.move_to(target)  # This blocks for ~2-3 seconds
   ```
4. Observe latency measurements continue without interruption

**Expected:**
- State stream continues at ~1kHz during move_to()
- No "timeout" or "no data" messages in latency script
- Latency remains <10ms throughout

**Pass Criteria:** ✅ State streaming never stops during blocking move

---

## Test 2: Joint Absolute Mode Data Collection
**Purpose:** Verify data collection in joint_abs mode with SpaceMouse

**Steps:**
1. Run: `python -m franka_control.scripts.collect_episodes --robot-ip <CONTROL_IP> --control-mode joint_abs --device spacemouse --dataset-root /tmp/test_joint_abs --repo-id test/joint_abs --fps 30`
2. Complete 2 episodes:
   - Episode 1: Move robot smoothly, mark as success
   - Episode 2: Move erratically, mark as failure
3. Check dataset structure:
   ```bash
   ls /tmp/test_joint_abs/data/
   # Should see: chunk-000/
   cat /tmp/test_joint_abs/meta/episode_annotations.json
   ```

**Expected:**
- Episode 0: success=true in annotations
- Episode 1: success=false in annotations
- Action shape: (N, 8) in Parquet files
- Action names: q0-q6, gripper
- State observation shape: (N, 7) for joint_pos

**Pass Criteria:** ✅ Both episodes recorded, annotations correct, action dimension=8

---

## Test 3: End-Effector Delta Mode Data Collection
**Purpose:** Verify data collection in ee_delta mode with keyboard

**Steps:**
1. Run: `python -m franka_control.scripts.collect_episodes --robot-ip <CONTROL_IP> --control-mode ee_delta --device keyboard --dataset-root /tmp/test_ee_delta --repo-id test/ee_delta --fps 10`
2. Complete 1 episode using keyboard controls (WASD, QE, RF, Space)
3. Verify action scaling: delta actions should be small (~0.01-0.1 range)

**Expected:**
- Action shape: (N, 7) in Parquet
- Action names: x, y, z, rx, ry, rz, gripper
- Delta actions scaled by dt (0.1s at 10Hz)
- Smooth motion without jerks

**Pass Criteria:** ✅ Episode recorded, action dimension=7, delta scaling correct

---

## Test 4: Gripper Command Recording
**Purpose:** Verify gripper records command values (not sensor feedback)

**Steps:**
1. Run joint_abs collection with binary gripper
2. During episode, press gripper close button (SpaceMouse button 0 or keyboard Space)
3. Immediately check action values in real-time (add print statement if needed)
4. After episode, inspect Parquet file:
   ```python
   import pandas as pd
   df = pd.read_parquet("/tmp/test_joint_abs/data/chunk-000/episode_0000.parquet")
   print(df["action.gripper"].unique())
   ```

**Expected:**
- Action gripper column shows discrete values: 0.0 (close) and 1.0 (open)
- Values change immediately when button pressed (not delayed by grasp duration)
- No intermediate values like 0.5 or 0.042

**Pass Criteria:** ✅ Gripper action is command value, not sensor feedback

---

## Test 5: Camera Integration
**Purpose:** Verify multi-camera recording with proper frame sync

**Steps:**
1. Connect 2 RealSense cameras, note serial numbers
2. Run: `python -m franka_control.scripts.collect_episodes --robot-ip <CONTROL_IP> --control-mode joint_abs --device spacemouse --dataset-root /tmp/test_cameras --repo-id test/cameras --camera-serials <SERIAL1> <SERIAL2> --camera-names wrist top --fps 30`
3. Complete 1 episode with robot motion
4. Check video files:
   ```bash
   ls /tmp/test_cameras/videos/
   # Should see: chunk-000/episode_0000-observation.images.wrist.mp4
   #             chunk-000/episode_0000-observation.images.top.mp4
   ```

**Expected:**
- Both video files created
- Videos have same frame count as Parquet rows
- No "Missing camera frame" warnings
- Frame timestamps in Parquet match video frame indices

**Pass Criteria:** ✅ Multi-camera recording works, frame counts match

---

## Test 6: Episode Discard on Camera Failure
**Purpose:** Verify episode auto-discards when camera frames missing

**Steps:**
1. Start collection with cameras
2. During episode, physically disconnect one camera
3. Continue moving robot
4. End episode

**Expected:**
- Console shows "Missing camera frame" warning
- Episode automatically discarded (not saved)
- No corrupted Parquet/video files

**Pass Criteria:** ✅ Episode discarded, no partial data saved

---

## Test 7: Applied Action Clipping
**Purpose:** Verify recorded actions are clipped, not raw teleop output

**Steps:**
1. Run ee_delta collection
2. Give extreme teleop input (push SpaceMouse to maximum)
3. Inspect recorded actions:
   ```python
   df = pd.read_parquet("/tmp/test_ee_delta/data/chunk-000/episode_0000.parquet")
   print(df[["action.x", "action.y", "action.z"]].describe())
   ```

**Expected:**
- Action values within FrankaEnv action_space bounds
- No values exceeding ±0.1 for delta modes
- Clipping applied before recording

**Pass Criteria:** ✅ Actions clipped to action_space limits

---

## Test 8: Annotation Persistence
**Purpose:** Verify episode annotations saved correctly

**Steps:**
1. Collect 3 episodes with different success labels
2. Close collector (finalize)
3. Read annotations:
   ```python
   import json
   with open("/tmp/test_joint_abs/meta/episode_annotations.json") as f:
       annotations = json.load(f)
   print(annotations)
   ```

**Expected:**
- JSON contains 3 entries
- Each entry has: episode_index, instruction, success, timestamp
- Success values match user input during collection

**Pass Criteria:** ✅ Annotations file correct, all episodes listed

---

## Test 9: LeRobot Dataset Loading
**Purpose:** Verify dataset compatible with LeRobot v3.0 API

**Steps:**
1. After collecting dataset, load with LeRobot:
   ```python
   from lerobot.common.datasets.lerobot_dataset import LeRobotDataset
   dataset = LeRobotDataset(repo_id="test/joint_abs", root="/tmp/test_joint_abs")
   print(f"Episodes: {dataset.num_episodes}")
   print(f"Frames: {dataset.num_frames}")
   sample = dataset[0]
   print(f"Action shape: {sample['action'].shape}")
   ```

**Expected:**
- Dataset loads without errors
- num_episodes matches collected count
- Action shape matches control_mode (8 for joint, 7 for ee)
- Observation keys present: joint_pos, ee_pos, ee_quat, gripper_width

**Pass Criteria:** ✅ LeRobot can load and iterate dataset

---

## Test 10: Long Episode Stress Test
**Purpose:** Verify system handles long episodes without memory issues

**Steps:**
1. Run collection at 30 Hz
2. Record single episode for 5 minutes (~9000 frames)
3. Monitor memory usage during recording
4. Finalize and check file sizes

**Expected:**
- No memory leaks or OOM errors
- Parquet file size reasonable (~10-50 MB)
- Video files encoded correctly
- No frame drops or corruption

**Pass Criteria:** ✅ Long episode completes, files valid

---

## Summary Checklist
- [ ] Test 1: State streaming during blocking ops
- [ ] Test 2: Joint absolute mode collection
- [ ] Test 3: EE delta mode collection
- [ ] Test 4: Gripper command recording
- [ ] Test 5: Multi-camera integration
- [ ] Test 6: Episode discard on camera failure
- [ ] Test 7: Applied action clipping
- [ ] Test 8: Annotation persistence
- [ ] Test 9: LeRobot dataset loading
- [ ] Test 10: Long episode stress test

## Notes
- Run tests in order (Test 1 is prerequisite for others)
- Keep control/gripper servers running between tests
- Clean /tmp/test_* directories between tests to avoid conflicts
- Document any failures with error messages and logs
