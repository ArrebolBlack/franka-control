# Release Materials Checklist

本清单列出 `v0.1.0` 发布和 Franka Community 提交前仍需要从真实 FR3
实验现场获得的资料。每一项都说明需要什么、为什么需要、以及如何获得。

收集原则：

- 只记录真实硬件和真实运行结果，不用模拟结果替代硬件验证。
- 图片、GIF、视频中不要出现人脸、私人白板、内网地址、门牌、设备资产编号等敏感信息。
- 第一次让机器人运动时使用低速、小范围动作，并确保急停可触达。
- 收集完成后，把文字结果回填到 `docs/hardware_validation.md`，把媒体文件放到
  `docs/assets/`，把发布/提交信息回填到 `docs/community_submission.md` 和
  `CHANGELOG.md`。

## 1. 网络与硬件基础信息

| 需要什么 | 为什么需要 | 我该如何获得 |
|---|---|---|
| Franka FCI IP，也就是 `--fci-ip` | `RobotServer` 必须从控制 PC 直连 FCI；文档需要避免把 FCI IP 和控制 PC IP 混淆。 | 在 Franka Desk、机器人网络设置、或实验室网络记录中查看；也可以询问维护机器人网络的人。只记录到 `docs/hardware_validation.md`，不要出现在公开视频里。 |
| 控制 PC IP，也就是算法 PC 使用的 `--robot-ip` | 算法 PC 的 teleop、latency、data collection 都通过这个地址连接 `RobotServer`。 | 在控制 PC 上运行 `ip addr` 或 `hostname -I`，确认与算法 PC 位于同一控制网络。 |
| 算法 PC IP | 用于记录双机网络拓扑，排查连通性和端口方向。 | 在算法 PC 上运行 `ip addr` 或 `hostname -I`；如果有多块网卡，记录连接控制网络的那一个。 |
| Gripper 服务地址和端口，也就是 `--gripper-host` / `--gripper-port` | 数据采集和 teleop 需要知道夹爪服务是否与机器人服务同机，以及是否使用默认端口 `5556`。 | 通常 `--gripper-host` 等于控制 PC IP；如果修改过端口，记录实际启动 `GripperServer` 时的参数。 |
| Robot RPC、Gripper RPC、State Stream 端口 | 这些端口决定 ZMQ 通信是否能连通，也用于排查端口冲突。 | 记录启动命令中的 `--port`、`--state-stream-port`；默认是 `5555`、`5556`、`5557`。 |
| 机器人型号 | 发布材料必须明确真实验证对象，当前目标是 Franka Research 3。 | 从机器人铭牌、采购记录、Franka Desk 或实验室设备登记中确认，写入硬件验证表。 |
| Franka 系统版本 | 不同系统版本可能影响 FCI 行为和兼容性。 | 在 Franka Desk 或机器人管理界面查看完整版本号，截图或文字记录即可。 |
| Franka Hand / gripper 型号和状态 | 夹爪验证、数据集动作维度、抓取 demo 都依赖夹爪硬件。 | 在设备清单或 Franka Desk 中确认；同时记录夹爪是否能 homing、open、close。 |
| 控制 PC 操作系统版本 | 控制 PC 承担实时控制侧依赖，OS 版本会影响安装和运行。 | 在控制 PC 上运行 `lsb_release -a` 或 `cat /etc/os-release`。 |
| 控制 PC kernel / PREEMPT_RT 版本 | 真实控制稳定性和 reviewer 信任度依赖实时内核信息。 | 在控制 PC 上运行 `uname -a`；如果使用 PREEMPT_RT，记录完整 kernel 字符串。 |
| 控制 PC Python 版本和关键依赖版本 | `aiofranka`、`pylibfranka` 等控制侧依赖是否可用需要被记录。 | 在控制 PC 仓库环境中运行 `python scripts/collect_validation_info.py --format markdown`，复制输出到硬件验证资料中。 |
| 算法 PC 操作系统版本 | 算法 PC 运行相机、teleop、数据采集和 dataset player，OS/GUI 环境会影响结果。 | 在算法 PC 上运行 `lsb_release -a` 或 `cat /etc/os-release`。 |
| 算法 PC Python 版本和关键依赖版本 | 证明数据采集、相机、LeRobot、OpenCV 等软件环境可复现。 | 在算法 PC 仓库环境中运行 `python scripts/collect_validation_info.py --format markdown --probe-realsense`。 |
| RealSense 相机型号、序列号、固件版本、USB 连接方式 | 多相机数据采集需要精确序列号；固件/USB 信息能帮助排查丢帧和带宽问题。 | 优先运行 `python scripts/collect_validation_info.py --format markdown --probe-realsense`；也可以用 `rs-enumerate-devices` 交叉确认。 |
| `config/cameras.yaml` 中的最终相机配置 | 数据采集命令依赖这个文件；README demo 需要能复现同样的相机视角。 | 打开并核对 `config/cameras.yaml`，确认名称、序列号、分辨率、FPS 与真实设备一致。 |
| Teleop 设备型号 | README 和硬件验证需要说明 keyboard / SpaceMouse 的真实设备条件。 | 记录键盘类型；SpaceMouse 可通过 `lsusb`、设备包装、系统设置或实验室设备登记确认型号。 |
| SpaceMouse Linux 权限状态 | 如果 SpaceMouse 权限未配置，teleop demo 会失败。 | 插入 SpaceMouse 后运行相关 teleop 命令；如失败，按 README 中 udev 规则配置后记录结果。 |

## 2. 自动采集输出

| 需要什么 | 为什么需要 | 我该如何获得 |
|---|---|---|
| 控制 PC 的环境采集输出 | 用同一工具记录 OS、Python、git、包版本，减少手工漏项。 | 在控制 PC 的仓库环境运行：`python scripts/collect_validation_info.py --format markdown`。把输出粘贴到 `docs/hardware_validation.md` 的验证记录或附录中。 |
| 算法 PC 的环境采集输出 | 算法 PC 负责相机和数据集工具，需要单独记录。 | 在算法 PC 的仓库环境运行：`python scripts/collect_validation_info.py --format markdown --probe-realsense`。 |
| 两台机器的仓库 commit hash | 确认硬件验证对应的是哪个版本的代码。 | 自动采集输出里会包含 git 信息；也可以运行 `git rev-parse HEAD`。控制 PC 和算法 PC 应尽量使用同一个 commit。 |
| 两台机器的完整验证日期和操作者 | 让验证记录可追溯，发布时能说明何时、由谁完成。 | 在执行硬件验证当天记录日期、姓名或实验室内部代号，并写入 `docs/hardware_validation.md`。 |

## 3. 硬件验证结果

| 需要什么 | 为什么需要 | 我该如何获得 |
|---|---|---|
| `RobotServer` 启动成功记录 | 证明控制 PC 能连上真实 FR3 FCI。 | 在控制 PC 运行 `python -m franka_control.robot --fci-ip <FCI_IP> --port 5555 --state-stream-port 5557 --poll-hz 1000`，保存启动日志和是否持续运行。 |
| `GripperServer` 启动成功记录 | 证明夹爪服务可用。 | 在控制 PC 另一个终端运行 `python -m franka_control.gripper --robot-ip <FCI_IP> --port 5556 --poll-hz 50`，保存启动日志。 |
| latency measurement 结果 | 证明算法 PC 到控制 PC 的 RPC/状态通信延迟在可接受范围内。 | 在算法 PC 运行 `python -m franka_control.scripts.measure_latency --robot-ip <CONTROL_PC_IP> -n 100`，记录 min/mean/max 或命令完整输出。 |
| 低速 keyboard teleop 验证 | keyboard 是最基础的 teleop 路径，需要证明能安全移动。 | 清空工作区后运行低速 teleop：`python -m franka_control.scripts.teleop --robot-ip <CONTROL_PC_IP> --gripper-host <CONTROL_PC_IP> --device keyboard --action-scale-t 0.5 --action-scale-r 1.0 --hz 50`。记录结果和是否触发急停。 |
| 低速 SpaceMouse teleop 验证 | SpaceMouse 是主要演示交互方式之一，也能暴露 HID 权限问题。 | 插入 SpaceMouse 后用低速参数运行 `teleop --device spacemouse`，记录设备型号、权限是否正常、运动是否平滑。 |
| waypoint collection 验证 | 证明 waypoint 工作流可从真实机器人采点并保存。 | 运行 `python -m franka_control.scripts.collect_waypoints ...`，保存生成的 YAML 路径，例如 `config/waypoints.yaml`，并记录采点数量。 |
| trajectory dry-run 输出 | dry-run 不移动机器人，但证明 waypoint/轨迹配置可解析。 | 运行 `python -m franka_control.scripts.run_trajectory ... --dry-run`，保存命令和输出。 |
| 安全 trajectory execution 结果 | 证明真实轨迹执行链路可用。 | 使用低速度、低加速度、短距离路线运行 `run_trajectory`；记录速度/加速度 scale、是否安全完成、是否需要人工干预。 |
| camera preview 结果 | 证明 RealSense 配置、OpenCV GUI、相机带宽都能工作。 | 在算法 PC 运行带 `--cameras config/cameras.yaml --display auto` 的采集命令，确认所有相机画面可见。 |
| 带相机的数据采集结果 | README demo 和 LeRobot 数据集功能需要真实多模态数据。 | 运行一次短采集：`python -m franka_control.scripts.collect_episodes --robot-ip <CONTROL_PC_IP> --gripper-host <CONTROL_PC_IP> --repo-id test/franka_media --root data/franka_media --task-name "media capture validation" --device keyboard --control-mode ee_delta --action-scale-t 0.5 --action-scale-r 1.0 --fps 30 --num-episodes 1 --cameras config/cameras.yaml --display auto`。如果目录已存在，使用 `--resume` 或换新的 `--repo-id` / `--root`。 |
| `--no-camera` 数据采集结果 | 用来隔离机器人状态/action 写入链路，不受相机问题影响。 | 运行 `collect_episodes` 并加 `--action-scale-t 0.5 --action-scale-r 1.0 --no-camera --display off`，记录数据集路径和是否成功写入。 |
| dataset player 可播放结果 | 证明采集出的 LeRobot 数据集能被回放和检查。 | 运行 `python scripts/play_dataset.py --repo-id test/franka_media --root data/franka_media`，确认窗口、HUD、帧切换、播放控制可用。 |
| blocking gripper 不冻结相机帧的验证 | 这是数据同步质量风险点，抓取动作不能导致保存的数据集视频长时间卡住。 | 已确认：带相机采集时执行夹爪 open/close/grasp，CV2 实时窗口可能阻塞，但保存的数据集正常。后续如复测，应以保存的数据集帧连续性为准，不只看实时预览。 |
| 任何失败项的完整日志 | 失败也有价值，能避免文档过度承诺。 | 保存命令、完整错误、机器人是否移动、是否急停、恢复方式；不要删除失败记录，只把状态标为 pending 或 failed。 |

## 4. 图片、GIF、视频 Demo

| 需要什么 | 为什么需要 | 我该如何获得 |
|---|---|---|
| `docs/assets/system-architecture.png` 最终确认 | 架构图已存在，但发布前需要确认它仍符合真实双机部署。 | 打开图片检查 IP/端口概念是否与真实部署一致；如果一致，无需重录。 |
| `docs/assets/keyboard-teleop-install-gear.mp4` | README 需要展示 keyboard 遥操作可以完成精密装配任务。 | 已采集键盘遥操作安装齿轮 demo；发布前检查画面不包含敏感信息。 |
| `docs/assets/spacemouse-teleop-pouring.mp4` | README 需要展示 SpaceMouse 连续 6-DoF 遥操作能力。 | 已采集 SpaceMouse 倒水 demo；发布前检查画面不包含敏感信息。 |
| `docs/assets/dataset-player-fruit-basket.mp4` | 证明采集完成后可以用 dataset player 回放真实 LeRobot 数据集。 | 已采集水果放入篮子的 dataset playback demo；确认 HUD/播放信息可读。 |
| `docs/assets/trajectory-analysis.png` | 证明数据集轨迹可视化可用。 | 已用 dataset player 的 `v` 控制生成 trajectory figure。 |
| `docs/assets/action-distribution.png` | 证明数据集 action distribution 分析可用。 | 已用 dataset player 的 `a` 控制生成 action distribution figure。 |
| 可选 `docs/assets/data-collection-preview.gif` | 实时 OpenCV preview 可以展示采集过程，但信息量低于 dataset playback。 | 非 `v0.1.0` 必需项；如后续补充，只录预览窗口并避免敏感信息。 |
| 可选 `docs/assets/waypoint-route.png` | waypoint/trajectory 工作流如果要在 README 中突出展示，需要路线图或界面截图。 | 完成 waypoint collection 后截取路线/可视化结果；如果没有清晰画面，可以不作为 v0.1.0 必需项。 |
| 可选公开视频 demo URL | Franka Community 提交通常比单个 GIF 更适合引用一个完整 demo 链接。 | 录制 30-90 秒横屏视频，内容包括 teleop、采集预览、dataset player。上传到 GitHub Release、YouTube、Bilibili 或实验室可公开链接，确认无需登录即可访问。 |
| 可选本地 demo MP4 | 如果暂时不上传公开视频，GitHub Release 可附加 MP4。 | 使用 OBS、系统录屏或手机三脚架录制；文件名建议 `franka-control-v0.1.0-demo.mp4`，发布前检查声音、画面和隐私信息。 |
| README 媒体区最终截图检查 | 媒体文件存在不等于 README 渲染正确。 | 把素材放入 `docs/assets/` 后，打开 GitHub 或本地 Markdown 预览，确认 GIF/PNG 路径、尺寸、说明文字都正常。 |

## 5. 发布和提交信息

| 需要什么 | 为什么需要 | 我该如何获得 |
|---|---|---|
| 最终短项目描述 | Franka Community 邮件、GitHub Release、README 摘要需要一致表达。 | 如果现有描述不用改，可沿用 `docs/community_submission.md` 中的版本；如果要突出实验室任务或应用场景，请提供 1-2 句话。 |
| `v0.1.0` release notes 中的 tested hardware 段落 | Release 需要明确这个版本真实测试过什么硬件。 | 从填好的 `docs/hardware_validation.md` 摘取机器人型号、系统版本、两台 PC、相机、teleop 设备、FPS 和控制模式。 |
| GitHub Release URL | Franka Community 提交需要引用稳定版本。 | 硬件验证和媒体完成后创建 `v0.1.0` GitHub Release，复制 release 页面 URL。 |
| Demo URL 或 GIF 路径 | Franka Community reviewer 需要快速看到真实运行效果。 | 优先提供公开视频 URL；如果没有，使用 README 中的 GIF/PNG 路径和 GitHub Release 附件。 |
| 提交人姓名、邮箱、单位或项目归属 | 提交邮件需要明确联系人。 | 提供你希望公开使用的姓名、联系邮箱、实验室/学校/公司名称；如果只用个人身份提交，也请确认署名方式。 |
| 是否允许公开硬件验证信息 | 硬件验证会暴露设备和系统信息，需要发布前确认。 | 检查 `docs/hardware_validation.md`，确认 IP、用户名、内网路径、序列号等是否需要脱敏。 |
| 是否允许公开图片、GIF、视频 | 媒体可能包含环境隐私，需要最终授权。 | 对每个媒体文件逐一检查背景、屏幕、白板、人脸、设备标签，确认可以公开后再提交。 |
| 最终提交日期 | 便于记录项目进度和追踪 Franka Community 提交流程。 | 发送邮件当天记录日期，并在 `progress.md` / `todo.md` 中更新状态。 |

## 6. 推荐收集顺序

1. 在控制 PC 和算法 PC 上拉取同一个 commit，并运行环境采集命令。
2. 确认 FCI IP、控制 PC IP、算法 PC IP、端口和相机配置。
3. 启动 `RobotServer` 和 `GripperServer`，保存日志。
4. 从算法 PC 运行 latency measurement，记录结果。
5. 先做低速 keyboard teleop，再做低速 SpaceMouse teleop。
6. 验证 waypoint collection、trajectory dry-run 和一条短距离安全轨迹。
7. 验证 camera preview，然后用保守 `--action-scale-t` / `--action-scale-r`
   采集一集带相机的短数据。
8. 再用相同速度限制采集一集 `--no-camera` 数据，隔离验证 robot/action
   写入链路。
9. 打开 dataset player，截取 dataset player 和 trajectory/action analysis 图片。
10. 放入 keyboard teleop、SpaceMouse teleop、dataset playback 视频和
    trajectory/action analysis 图片。
11. 回填 `docs/hardware_validation.md`，放入 `docs/assets/`，更新 README 媒体区。
12. 跑最终检查后创建 release，再准备 Franka Community 提交。

## 7. 资料放置位置

| 资料类型 | 放置位置 |
|---|---|
| 硬件矩阵、验证 checklist、日期、操作者、命令输出摘要 | `docs/hardware_validation.md` |
| keyboard teleop 视频 | `docs/assets/keyboard-teleop-install-gear.mp4` |
| SpaceMouse teleop 视频 | `docs/assets/spacemouse-teleop-pouring.mp4` |
| dataset player 视频 | `docs/assets/dataset-player-fruit-basket.mp4` |
| trajectory figure | `docs/assets/trajectory-analysis.png` |
| action distribution figure | `docs/assets/action-distribution.png` |
| 可选 data collection preview GIF | `docs/assets/data-collection-preview.gif` |
| 可选 waypoint/route 截图 | `docs/assets/waypoint-route.png` |
| 可选完整 demo 视频 | GitHub Release 附件或公开视频 URL |
| release notes | `CHANGELOG.md` 和 GitHub Release 页面 |
| Franka Community 提交邮件和描述 | `docs/community_submission.md` |
| 当前执行状态 | `progress.md`、`todo.md`、`acceptance.md`、`plan.md` |

## 8. 收集完成后的本地检查

```bash
python scripts/check_markdown_links.py
git diff --check
python -m pytest tests -q
```

如果只更新文档和图片，至少运行前两项；如果硬件验证过程中发现代码或 CLI
参数需要修改，再运行完整测试。
