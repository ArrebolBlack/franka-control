"""Dataset Player - 完整版

支持播放、导航、过滤、截图、进度条、状态显示、轨迹可视化、action 分析、视频导出

Usage:
    python scripts/play_dataset.py --repo-id test/cameras --root /tmp/test_cameras
"""

from __future__ import annotations

# ============================================================================
# Part 1: Imports & Constants
# ============================================================================
import argparse
import json
import time
from pathlib import Path

try:
    import cv2
    import numpy as np
    import matplotlib.pyplot as plt
    from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
    from lerobot.datasets.lerobot_dataset import LeRobotDataset
except ImportError as _runtime_import_error:
    cv2 = None
    np = None
    plt = None
    LeRobotDataset = None
else:
    _runtime_import_error = None

# 速度档位
SPEED_LEVELS = [0.25, 0.5, 1.0, 2.0, 4.0]
DEFAULT_SPEED_IDX = 2  # 1.0x

# 过滤模式
FILTER_MODES = ["all", "success", "failure", "by_task"]


# ============================================================================
# Part 2: Data Layer - Episode 数据管理
# ============================================================================
class EpisodeInfo:
    """单个 episode 的元数据"""

    def __init__(self, idx: int, start_frame: int, end_frame: int,
                 task: str, success: bool):
        self.idx = idx
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.num_frames = end_frame - start_frame
        self.task = task
        self.success = success


class DatasetPlayer:
    """数据集播放器 - 管理 episode 和帧数据"""

    def __init__(self, repo_id: str, root: str):
        self.dataset = LeRobotDataset(repo_id, root=root)
        self.root = Path(root)
        self.episodes = self._load_episodes()

        # 播放状态
        self.current_episode_idx = 0
        self.current_frame_idx = 0  # 相对于 episode 内的帧索引
        self.playing = False
        self.speed_idx = DEFAULT_SPEED_IDX

        # 过滤状态
        self.filter_mode = "all"
        self.filter_task = None
        self.filtered_episodes = list(range(len(self.episodes)))

    def _load_episodes(self) -> list[EpisodeInfo]:
        """从 dataset.meta.episodes 构建 episode 边界"""
        # 读取 success 标注
        annotations = self._load_annotations()

        episodes = []

        # 使用 dataset.meta.episodes 获取边界
        if hasattr(self.dataset, 'meta') and hasattr(self.dataset.meta, 'episodes'):
            # LeRobot v3.0 格式：meta.episodes 是 HuggingFace Dataset
            meta_episodes = self.dataset.meta.episodes

            for i in range(len(meta_episodes)):
                ep_meta = meta_episodes[i]

                # 字段名是 dataset_from_index / dataset_to_index
                start = ep_meta['dataset_from_index']
                end = ep_meta['dataset_to_index']

                # tasks 是列表，取第一个
                task = ep_meta['tasks'][0] if ep_meta['tasks'] else "unknown"

                # episode_index 就是索引
                ep_idx = ep_meta['episode_index']

                success = annotations.get(str(ep_idx), {}).get("success", True)
                episodes.append(EpisodeInfo(
                    idx=ep_idx,
                    start_frame=start,
                    end_frame=end,
                    task=task,
                    success=success,
                ))
        else:
            # 回退方案：遍历所有帧（慢）
            episodes_dict = {}
            for i in range(self.dataset.num_frames):
                ep_idx = self.dataset[i]["episode_index"].item()
                if ep_idx not in episodes_dict:
                    episodes_dict[ep_idx] = {
                        "start": i,
                        "end": i + 1,
                        "task": self.dataset[i]["task"],
                    }
                else:
                    episodes_dict[ep_idx]["end"] = i + 1

            for ep_idx in sorted(episodes_dict.keys()):
                ep_data = episodes_dict[ep_idx]
                success = annotations.get(str(ep_idx), {}).get("success", True)
                episodes.append(EpisodeInfo(
                    idx=ep_idx,
                    start_frame=ep_data["start"],
                    end_frame=ep_data["end"],
                    task=ep_data["task"],
                    success=success,
                ))

        return episodes

    def _load_annotations(self) -> dict:
        """读取 episode success 标注"""
        ann_path = self.root / "meta" / "episode_annotations.json"
        if ann_path.exists():
            return json.loads(ann_path.read_text())
        return {}

    def get_current_episode(self) -> EpisodeInfo:
        """返回当前 episode 信息"""
        real_idx = self.filtered_episodes[self.current_episode_idx]
        return self.episodes[real_idx]

    def get_frame_data(self) -> dict:
        """返回当前帧的数据 {images, obs, action, task}"""
        episode = self.get_current_episode()
        abs_frame_idx = episode.start_frame + self.current_frame_idx

        frame = self.dataset[abs_frame_idx]

        # 提取相机图像
        images = {}
        for key in frame.keys():
            if key.startswith("observation.images."):
                cam_name = key.split(".")[-1]
                img_tensor = frame[key]
                # 转换为 numpy HWC uint8
                img = img_tensor.numpy() if hasattr(img_tensor, "numpy") else np.array(img_tensor)
                if img.ndim == 3 and img.shape[0] in (1, 3):
                    img = np.transpose(img, (1, 2, 0))
                if img.dtype != np.uint8:
                    img = (np.clip(img, 0, 1) * 255).astype(np.uint8)
                images[cam_name] = img

        # 提取 obs
        state = frame["observation.state"].numpy()
        ee_pose = frame["observation.ee_pose"].numpy()
        obs = {
            "joint_pos": state[:7],
            "gripper_width": state[7],
            "joint_vel": frame["observation.joint_vel"].numpy(),
            "ee_pos": ee_pose[:3],
            "ee_quat": ee_pose[3:],
            "effort": frame["observation.effort"].numpy(),
        }

        # 提取 action
        action = frame["action"].numpy()

        return {"images": images, "obs": obs, "action": action, "task": frame["task"]}

    def get_episode_arrays(self, ep_idx: int) -> dict:
        """获取 episode 的所有数组（不解码图像），用于分析"""
        episode = self.episodes[ep_idx]

        # 使用 select_columns 避免解码图像
        columns = [
            "observation.state",
            "observation.joint_vel",
            "observation.ee_pose",
            "action",
        ]

        joint_pos_list = []
        joint_vel_list = []
        ee_pos_list = []
        ee_quat_list = []
        gripper_list = []
        action_list = []

        # 直接访问 hf_dataset 避免图像解码
        for i in range(episode.start_frame, episode.end_frame):
            # 使用底层 dataset 访问，只读需要的列
            frame = self.dataset.hf_dataset[i]

            state = np.array(frame["observation.state"])
            joint_pos_list.append(state[:7])
            gripper_list.append(state[7])

            joint_vel_list.append(np.array(frame["observation.joint_vel"]))

            ee_pose = np.array(frame["observation.ee_pose"])
            ee_pos_list.append(ee_pose[:3])
            ee_quat_list.append(ee_pose[3:])

            action_list.append(np.array(frame["action"]))

        return {
            "joint_pos": np.array(joint_pos_list),
            "joint_vel": np.array(joint_vel_list),
            "ee_pos": np.array(ee_pos_list),
            "ee_quat": np.array(ee_quat_list),
            "gripper": np.array(gripper_list),
            "action": np.array(action_list),
        }

    def next_frame(self) -> bool:
        """前进一帧，返回是否成功前进"""
        episode = self.get_current_episode()
        self.current_frame_idx += 1
        if self.current_frame_idx >= episode.num_frames:
            # 尝试跳到下一个 episode
            if self.next_episode():
                return True
            # 最后一个 episode，clamp 到末尾并停止播放
            self.current_frame_idx = episode.num_frames - 1
            self.playing = False
            return False
        return True

    def prev_frame(self) -> None:
        """后退一帧"""
        self.current_frame_idx = max(0, self.current_frame_idx - 1)

    def next_episode(self) -> bool:
        """跳到下一个 episode"""
        if self.current_episode_idx < len(self.filtered_episodes) - 1:
            self.current_episode_idx += 1
            self.current_frame_idx = 0
            return True
        return False

    def prev_episode(self) -> None:
        """跳到上一个 episode"""
        if self.current_episode_idx > 0:
            self.current_episode_idx -= 1
            self.current_frame_idx = 0

    def jump_to_episode(self, idx: int) -> None:
        """跳转到指定 episode（filtered_episodes 中的索引）"""
        if 0 <= idx < len(self.filtered_episodes):
            self.current_episode_idx = idx
            self.current_frame_idx = 0

    def jump_to_progress(self, progress: float) -> None:
        """跳转到当前 episode 的指定进度 (0.0-1.0)"""
        episode = self.get_current_episode()
        self.current_frame_idx = int(progress * episode.num_frames)
        self.current_frame_idx = min(self.current_frame_idx, episode.num_frames - 1)

    def set_filter(self, mode: str, task: str = None) -> None:
        """设置过滤模式并更新 filtered_episodes"""
        old_mode = self.filter_mode
        old_task = self.filter_task

        self.filter_mode = mode
        self.filter_task = task
        self._update_filter()

        # 检查是否为空
        if not self.filtered_episodes:
            print(f"Warning: No episodes match filter '{mode}', reverting to previous filter")
            self.filter_mode = old_mode
            self.filter_task = old_task
            self._update_filter()
            return

        self.current_episode_idx = 0
        self.current_frame_idx = 0

    def _update_filter(self) -> None:
        """根据 filter_mode 更新 filtered_episodes"""
        if self.filter_mode == "all":
            self.filtered_episodes = list(range(len(self.episodes)))
        elif self.filter_mode == "success":
            self.filtered_episodes = [i for i, ep in enumerate(self.episodes) if ep.success]
        elif self.filter_mode == "failure":
            self.filtered_episodes = [i for i, ep in enumerate(self.episodes) if not ep.success]
        elif self.filter_mode == "by_task":
            self.filtered_episodes = [i for i, ep in enumerate(self.episodes)
                                     if ep.task == self.filter_task]

    @property
    def speed(self) -> float:
        return SPEED_LEVELS[self.speed_idx]

    def speed_up(self) -> None:
        self.speed_idx = min(self.speed_idx + 1, len(SPEED_LEVELS) - 1)

    def speed_down(self) -> None:
        self.speed_idx = max(self.speed_idx - 1, 0)


# ============================================================================
# Part 3: View Layer - 显示渲染
# ============================================================================
class Viewer:
    """视图管理 - 多相机显示 + HUD"""

    def __init__(self, window_name: str = "Dataset Player"):
        self.window_name = window_name
        self.selected_camera = None  # None = 全部, 0-N = 单个相机
        self.hud_mode = "normal"  # "normal" or "detailed"

        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)

    def render(self, frame_data: dict, player: DatasetPlayer) -> np.ndarray:
        """渲染完整画面：相机 + HUD"""
        # 1. 渲染相机画面
        camera_view = self._render_cameras(frame_data["images"])

        # 2. 渲染 HUD（叠加在相机画面上方）
        hud_text = self._build_hud(frame_data, player)
        display = self._draw_hud(camera_view, hud_text)

        # 3. 渲染状态信息（图片下方）
        if self.hud_mode == "detailed":
            state_panel = self._render_state_panel(frame_data, display.shape[1])
            display = np.vstack([display, state_panel])

        return display

    def _render_cameras(self, images: dict[str, np.ndarray]) -> np.ndarray:
        """渲染相机画面（横向拼接或单相机）"""
        if not images:
            # 无图像时返回黑屏
            return np.zeros((480, 640, 3), dtype=np.uint8)

        if self.selected_camera is not None:
            # 单相机模式
            cam_names = list(images.keys())
            if self.selected_camera < len(cam_names):
                cam_name = cam_names[self.selected_camera]
                rgb = images[cam_name]
                return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

        # 多相机横向拼接
        frames = [cv2.cvtColor(img, cv2.COLOR_RGB2BGR) for img in images.values()]

        # 统一高度
        h = frames[0].shape[0]
        resized = []
        for frame in frames:
            if frame.shape[0] != h:
                w = int(frame.shape[1] * h / frame.shape[0])
                frame = cv2.resize(frame, (w, h))
            resized.append(frame)

        return np.hstack(resized)

    def _build_hud(self, frame_data: dict, player: DatasetPlayer) -> list[str]:
        """构建 HUD 文本行"""
        episode = player.get_current_episode()
        lines = [
            f"Episode: {player.current_episode_idx + 1}/{len(player.filtered_episodes)} "
            f"(Real: {episode.idx + 1}/{len(player.episodes)})",
            f"Task: {episode.task} | Success: {episode.success}",
            f"Frame: {player.current_frame_idx + 1}/{episode.num_frames} | "
            f"Speed: {player.speed}x | {'Playing' if player.playing else 'Paused'}",
        ]

        if player.filter_mode != "all":
            lines.append(f"Filter: {player.filter_mode}")

        # 简洁模式下显示 gripper
        if self.hud_mode == "normal":
            gripper = frame_data["obs"]["gripper_width"]
            lines.append(f"Gripper: {gripper:.4f}m")

        return lines

    def _draw_hud(self, image: np.ndarray, lines: list[str]) -> np.ndarray:
        """在图像上绘制 HUD 文本"""
        display = image.copy()
        y = 30
        for line in lines:
            cv2.putText(display, line, (10, y),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            y += 30
        return display

    def _render_state_panel(self, frame_data: dict, image_width: int) -> np.ndarray:
        """渲染状态面板（详细模式）- 紧凑横向布局"""
        obs = frame_data["obs"]
        action = frame_data["action"]

        # 计算面板尺寸
        line_height = 25
        panel_height = line_height * 6 + 20  # 6 行数据 + padding
        panel_width = image_width

        # 创建白色背景
        panel = np.ones((panel_height, panel_width, 3), dtype=np.uint8) * 255

        # 绘制文本（黑色）
        y = 20
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.5
        color = (0, 0, 0)  # 黑色
        thickness = 1

        # Joint positions (横向)
        joint_str = "Joint Pos: " + " ".join([f"{x:6.3f}" for x in obs["joint_pos"]])
        cv2.putText(panel, joint_str, (10, y), font, font_scale, color, thickness)
        y += line_height

        # Joint velocities (横向)
        vel_str = "Joint Vel: " + " ".join([f"{x:6.3f}" for x in obs["joint_vel"]])
        cv2.putText(panel, vel_str, (10, y), font, font_scale, color, thickness)
        y += line_height

        # EE position (横向)
        ee_pos_str = f"EE Pos: x={obs['ee_pos'][0]:6.3f} y={obs['ee_pos'][1]:6.3f} z={obs['ee_pos'][2]:6.3f}"
        cv2.putText(panel, ee_pos_str, (10, y), font, font_scale, color, thickness)
        y += line_height

        # EE quaternion (横向)
        ee_quat_str = "EE Quat: " + " ".join([f"{x:6.3f}" for x in obs["ee_quat"]])
        cv2.putText(panel, ee_quat_str, (10, y), font, font_scale, color, thickness)
        y += line_height

        # Gripper
        gripper_str = f"Gripper: {obs['gripper_width']:6.4f}m"
        cv2.putText(panel, gripper_str, (10, y), font, font_scale, color, thickness)
        y += line_height

        # Action (横向)
        action_str = "Action: " + " ".join([f"{x:6.3f}" for x in action])
        cv2.putText(panel, action_str, (10, y), font, font_scale, color, thickness)

        return panel

    def toggle_camera(self, cam_idx: int) -> None:
        """切换相机显示模式"""
        if cam_idx == 0:
            self.selected_camera = None  # 显示全部
        else:
            self.selected_camera = cam_idx - 1

    def toggle_hud_mode(self) -> None:
        """切换 HUD 模式"""
        self.hud_mode = "detailed" if self.hud_mode == "normal" else "normal"

    def close(self) -> None:
        cv2.destroyAllWindows()


# ============================================================================
# Part 4: Controller Layer - 交互控制
# ============================================================================
class Controller:
    """控制器 - 处理按键和播放循环"""

    def __init__(self, player: DatasetPlayer, viewer: Viewer,
                 visualizer: "Visualizer", exporter: "VideoExporter"):
        self.player = player
        self.viewer = viewer
        self.visualizer = visualizer
        self.exporter = exporter
        self.last_update = time.time()

        # 进度条
        self._updating_trackbar = False
        self._setup_trackbar()

    def _setup_trackbar(self) -> None:
        """创建进度条（带 guard 防止回调循环）"""
        def on_trackbar_change(value):
            if self._updating_trackbar:
                return
            progress = value / 1000.0
            self.player.jump_to_progress(progress)

        cv2.createTrackbar("Progress", self.viewer.window_name,
                          0, 1000, on_trackbar_change)

    def _update_trackbar(self) -> None:
        """更新进度条位置"""
        self._updating_trackbar = True
        episode = self.player.get_current_episode()
        if episode.num_frames > 1:
            progress = self.player.current_frame_idx / (episode.num_frames - 1)
            cv2.setTrackbarPos("Progress", self.viewer.window_name,
                              int(progress * 1000))
        self._updating_trackbar = False

    def handle_key(self, key: int) -> bool:
        """处理按键，返回 False 表示退出"""
        # 退出
        if key in (ord('q'), 27):  # q or Esc
            return False

        # 播放控制
        elif key == ord(' '):
            self.player.playing = not self.player.playing
        elif key == 2424832:  # 左箭头（waitKeyEx）
            self.player.playing = False
            self.player.prev_frame()
            self._update_trackbar()
        elif key == 2555904:  # 右箭头（waitKeyEx）
            self.player.playing = False
            self.player.next_frame()
            self._update_trackbar()
        elif key == ord(','):
            self.player.speed_down()
        elif key == ord('.'):
            self.player.speed_up()

        # Episode 导航
        elif key == ord('['):
            self.player.prev_episode()
            self._update_trackbar()
        elif key == ord(']'):
            self.player.next_episode()
            self._update_trackbar()
        elif key == 2359296:  # Home（waitKeyEx）
            self.player.current_frame_idx = 0
            self._update_trackbar()
        elif key == 2293760:  # End（waitKeyEx）
            episode = self.player.get_current_episode()
            self.player.current_frame_idx = episode.num_frames - 1
            self._update_trackbar()
        elif key == ord('g'):
            self._jump_to_episode_input()
            self._update_trackbar()

        # 视图控制
        elif ord('1') <= key <= ord('9'):
            self.viewer.toggle_camera(key - ord('0'))
        elif key == ord('0'):
            self.viewer.toggle_camera(0)
        elif key == ord('h'):
            self.viewer.toggle_hud_mode()

        # 过滤
        elif key == ord('f'):
            self._cycle_filter()
            self._update_trackbar()
        elif key == ord('t'):
            self._filter_by_task()
            self._update_trackbar()

        # Episode 列表
        elif key == ord('l'):
            self._show_episode_list()

        # 截图
        elif key == ord('p'):
            self._save_screenshot()

        # 可视化
        elif key == ord('v'):
            self.visualizer.show_trajectory()
        elif key == ord('a'):
            self.visualizer.show_action_distribution()
        elif key == ord('i'):  # info/statistics
            self.visualizer.show_statistics_table()

        # 视频导出
        elif key == ord('s'):
            self.exporter.export_episode(self.player, self.viewer)
            self._update_trackbar()

        return True

    def _jump_to_episode_input(self) -> None:
        """终端输入 episode 跳转"""
        try:
            ep_idx = int(input("\nEnter episode index (real): "))
            # 查找 real episode index 在 filtered_episodes 中的位置
            for i, real_idx in enumerate(self.player.filtered_episodes):
                if self.player.episodes[real_idx].idx == ep_idx:
                    self.player.jump_to_episode(i)
                    print(f"Jumped to episode {ep_idx}")
                    return
            print(f"Episode {ep_idx} not found in current filter")
        except (ValueError, EOFError):
            print("Invalid input")

    def _cycle_filter(self) -> None:
        """循环切换过滤模式"""
        modes = ["all", "success", "failure"]
        idx = modes.index(self.player.filter_mode) if self.player.filter_mode in modes else 0
        next_mode = modes[(idx + 1) % len(modes)]
        self.player.set_filter(next_mode)
        print(f"\nFilter: {next_mode}")

    def _filter_by_task(self) -> None:
        """按 task 过滤"""
        # 收集所有 task
        tasks = sorted(set(ep.task for ep in self.player.episodes))
        print("\n" + "="*60)
        print("Available tasks:")
        for i, task in enumerate(tasks):
            print(f"  [{i}] {task}")
        print("="*60)

        try:
            idx = int(input("Select task index (or -1 for all): "))
            if idx == -1:
                self.player.set_filter("all")
                print("Filter: all")
            elif 0 <= idx < len(tasks):
                self.player.set_filter("by_task", tasks[idx])
                print(f"Filter: task={tasks[idx]}")
        except (ValueError, EOFError):
            print("Invalid input")

    def _show_episode_list(self) -> None:
        """显示 episode 列表（终端输出）"""
        print("\n" + "="*75)
        print("Episode List:")
        print("="*75)
        for i, ep_idx in enumerate(self.player.filtered_episodes):
            ep = self.player.episodes[ep_idx]
            marker = ">>>" if i == self.player.current_episode_idx else "   "
            print(f"{marker} [{i+1:3d}] Ep {ep.idx+1:3d}: {ep.task:25s} | "
                  f"Success: {str(ep.success):5s} | Frames: {ep.num_frames:4d}")
        print("="*75 + "\n")

    def _save_screenshot(self) -> None:
        """保存当前帧截图"""
        frame_data = self.player.get_frame_data()
        episode = self.player.get_current_episode()

        output_dir = Path("screenshots")
        output_dir.mkdir(exist_ok=True)

        for cam_name, image in frame_data["images"].items():
            filename = f"ep{episode.idx:03d}_frame{self.player.current_frame_idx:04d}_{cam_name}.png"
            filepath = output_dir / filename
            cv2.imwrite(str(filepath), cv2.cvtColor(image, cv2.COLOR_RGB2BGR))

        print(f"Screenshot saved to {output_dir}/")

    def update(self) -> None:
        """播放循环更新"""
        if not self.player.playing:
            return

        now = time.time()
        dt = now - self.last_update
        target_dt = (1.0 / 30.0) / self.player.speed

        if dt >= target_dt:
            self.player.next_frame()
            self.last_update = now
            self._update_trackbar()


# ============================================================================
# Part 5: Visualization Layer - 轨迹和 Action 分析
# ============================================================================
class Visualizer:
    """可视化工具 - 轨迹和 Action 分析"""

    def __init__(self, player: DatasetPlayer):
        self.player = player

    def show_trajectory(self) -> None:
        """显示轨迹可视化"""
        episode = self.player.get_current_episode()

        # 使用无副作用的数组获取
        arrays = self.player.get_episode_arrays(episode.idx)

        joint_traj = arrays["joint_pos"]
        ee_traj = arrays["ee_pos"]
        gripper_traj = arrays["gripper"]

        # 创建图表
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle(f"Trajectory - Episode {episode.idx + 1}: {episode.task}",
                     fontsize=14)

        # Joint 轨迹（7 个子图）
        for i in range(7):
            ax = fig.add_subplot(3, 3, i + 1)
            ax.plot(joint_traj[:, i], linewidth=1.5)
            ax.set_title(f"Joint {i}")
            ax.set_xlabel("Frame")
            ax.set_ylabel("Angle (rad)")
            ax.grid(True, alpha=0.3)

        # EE 3D 轨迹
        ax = fig.add_subplot(3, 3, 8, projection='3d')
        colors = np.arange(len(ee_traj))
        scatter = ax.scatter(ee_traj[:, 0], ee_traj[:, 1], ee_traj[:, 2],
                            c=colors, cmap='viridis', s=10)
        ax.plot(ee_traj[:, 0], ee_traj[:, 1], ee_traj[:, 2],
               'gray', alpha=0.3, linewidth=0.5)
        ax.set_title("End-Effector 3D Trajectory")
        ax.set_xlabel("X (m)")
        ax.set_ylabel("Y (m)")
        ax.set_zlabel("Z (m)")
        plt.colorbar(scatter, ax=ax, label="Time", shrink=0.5)

        # Gripper 轨迹
        ax = fig.add_subplot(3, 3, 9)
        ax.plot(gripper_traj, linewidth=1.5)
        ax.set_title("Gripper Width")
        ax.set_xlabel("Frame")
        ax.set_ylabel("Width (m)")
        ax.grid(True, alpha=0.3)

        # 标注抓取/释放时刻（width 突变点）
        diff = np.abs(np.diff(gripper_traj))
        threshold = 0.01  # 突变阈值
        events = np.where(diff > threshold)[0]
        for event_idx in events:
            ax.axvline(event_idx, color='r', linestyle='--', alpha=0.5)

        plt.tight_layout()
        plt.show(block=True)

    def show_action_distribution(self) -> None:
        """显示 action 分布"""
        episode = self.player.get_current_episode()

        # 使用无副作用的数组获取
        arrays = self.player.get_episode_arrays(episode.idx)
        actions = arrays["action"]

        action_dim = actions.shape[1]

        # 创建图表
        fig = plt.figure(figsize=(16, 10))
        fig.suptitle(f"Action Distribution - Episode {episode.idx + 1}: {episode.task}",
                     fontsize=14)

        # 直方图（每个维度）
        for i in range(min(action_dim, 8)):
            ax = fig.add_subplot(3, 3, i + 1)
            ax.hist(actions[:, i], bins=30, alpha=0.7, edgecolor='black')

            dim_name = f"Dim {i}" if i < action_dim - 1 else "Gripper"
            ax.set_title(dim_name)
            ax.set_xlabel("Value")
            ax.set_ylabel("Count")
            ax.grid(True, alpha=0.3)

            # 统计信息
            mean = np.mean(actions[:, i])
            std = np.std(actions[:, i])
            ax.axvline(mean, color='r', linestyle='--', linewidth=2,
                      label=f'μ={mean:.3f}')
            ax.axvline(mean + std, color='orange', linestyle=':', linewidth=1.5)
            ax.axvline(mean - std, color='orange', linestyle=':', linewidth=1.5,
                      label=f'σ={std:.3f}')
            ax.legend(fontsize=8)

        # 时间序列（最后一个子图）
        ax = fig.add_subplot(3, 3, 9)
        for i in range(min(action_dim, 8)):
            dim_name = f"D{i}" if i < action_dim - 1 else "Grip"
            ax.plot(actions[:, i], label=dim_name, alpha=0.7, linewidth=1)
        ax.set_title("Action Time Series")
        ax.set_xlabel("Frame")
        ax.set_ylabel("Value")
        ax.legend(fontsize=8, ncol=2)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.show(block=True)

    def show_statistics_table(self) -> None:
        """打印统计表格"""
        episode = self.player.get_current_episode()

        # 使用无副作用的数组获取
        arrays = self.player.get_episode_arrays(episode.idx)
        actions = arrays["action"]

        action_dim = actions.shape[1]

        print("\n" + "="*85)
        print(f"Action Statistics - Episode {episode.idx + 1}: {episode.task}")
        print("="*85)
        print(f"{'Dimension':<12} {'Min':>10} {'Max':>10} {'Mean':>10} "
              f"{'Std':>10} {'Outliers':>10}")
        print("-"*85)

        for i in range(action_dim):
            data = actions[:, i]
            mean = np.mean(data)
            std = np.std(data)
            outliers = np.sum(np.abs(data - mean) > 3 * std)

            dim_name = f"Dim {i}" if i < action_dim - 1 else "Gripper"
            print(f"{dim_name:<12} {np.min(data):>10.4f} {np.max(data):>10.4f} "
                  f"{mean:>10.4f} {std:>10.4f} {outliers:>10d}")

        print("="*85 + "\n")


# ============================================================================
# Part 6: Export Layer - 视频导出
# ============================================================================
class VideoExporter:
    """视频导出工具"""

    @staticmethod
    def export_episode(player: DatasetPlayer, viewer: Viewer,
                      output_path: str = None) -> None:
        """导出当前 episode 为 MP4"""
        episode = player.get_current_episode()

        if output_path is None:
            output_dir = Path("videos")
            output_dir.mkdir(exist_ok=True)

            # 清理 task 名称（移除非法字符）
            safe_task = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_'
                               for c in episode.task)
            safe_task = safe_task.replace(' ', '_')

            output_path = output_dir / f"ep{episode.idx:03d}_{safe_task}.mp4"

        # 保存当前状态
        saved_frame_idx = player.current_frame_idx
        saved_playing = player.playing
        player.playing = False

        writer = None
        try:
            # 获取第一帧确定分辨率
            player.current_frame_idx = 0
            frame_data = player.get_frame_data()
            display = viewer.render(frame_data, player)
            h, w = display.shape[:2]

            # 创建 VideoWriter
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            fps = player.dataset.fps
            writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

            if not writer.isOpened():
                print(f"Failed to open VideoWriter for {output_path}")
                return

            print(f"\nExporting episode {episode.idx + 1} to {output_path}...")
            print(f"Total frames: {episode.num_frames}")

            # 逐帧写入
            for i in range(episode.num_frames):
                player.current_frame_idx = i
                frame_data = player.get_frame_data()
                display = viewer.render(frame_data, player)
                writer.write(display)

                if i % 30 == 0:
                    print(f"  Progress: {i}/{episode.num_frames}")

            print(f"Export complete: {output_path}\n")

        finally:
            if writer is not None:
                writer.release()

            # 恢复状态
            player.current_frame_idx = saved_frame_idx
            player.playing = saved_playing


# ============================================================================
# Part 7: Main Loop
# ============================================================================
def _ensure_runtime_dependencies() -> None:
    """Fail with a clear message after argparse has handled --help."""
    if _runtime_import_error is not None:
        raise SystemExit(
            "Dataset player requires OpenCV, NumPy, Matplotlib, and LeRobot. "
            f"Missing dependency: {_runtime_import_error}"
        )


def main():
    parser = argparse.ArgumentParser(description="Dataset Player - 完整版")
    parser.add_argument("--repo-id", required=True, help="Dataset repo ID")
    parser.add_argument("--root", required=True, help="Dataset root path")
    args = parser.parse_args()
    _ensure_runtime_dependencies()

    # 初始化
    print("Loading dataset...")
    player = DatasetPlayer(args.repo_id, args.root)
    viewer = Viewer()
    visualizer = Visualizer(player)
    exporter = VideoExporter()
    controller = Controller(player, viewer, visualizer, exporter)

    print(f"\nDataset loaded: {len(player.episodes)} episodes, {player.dataset.num_frames} frames")
    print("\nControls:")
    print("  Space: Play/Pause")
    print("  ←/→: Previous/Next frame")
    print("  [/]: Previous/Next episode")
    print("  g: Jump to episode (input)")
    print("  ,/.: Decrease/Increase speed")
    print("  Home/End: Jump to start/end")
    print("  1-9: Single camera, 0: All cameras")
    print("  h: Toggle HUD mode (normal/detailed)")
    print("  f: Cycle filter (all/success/failure)")
    print("  t: Filter by task")
    print("  l: Show episode list")
    print("  p: Save screenshot")
    print("  v: Show trajectory")
    print("  a: Show action distribution")
    print("  i: Show action statistics")
    print("  s: Export video")
    print("  q/Esc: Quit\n")

    # 主循环
    try:
        while True:
            # 获取数据
            frame_data = player.get_frame_data()

            # 渲染
            display = viewer.render(frame_data, player)
            cv2.imshow(viewer.window_name, display)

            # 处理按键（使用 waitKeyEx 支持扩展键）
            key = cv2.waitKeyEx(1)
            if key != -1:
                if not controller.handle_key(key):
                    break

            # 更新播放状态
            controller.update()

    finally:
        viewer.close()


if __name__ == "__main__":
    main()


