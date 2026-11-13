# 验证记录

初始记录日期：2026-11-02；后续修复与检查按下方日期分别记录。工作区位于 Windows，项目目标运行环境为 Ubuntu 22.04 + ROS2 Humble；历史检查不能代替当前版本的 Ubuntu 验收。

## 2026-11-02 本机实际执行

- 用 Zig 0.16.0 的 C++17 编译器编译了共享任务核心和预览桥接程序，运行通过 39 项任务不变量检查：巡逻索引、严格优先级、取消屏障、旧 token、同级 FIFO、嵌套恢复、去重、TTL、暂停/故障独立、取消超时、重试和队列/ID 历史上限。
- 13 项 Python 测试全部通过，覆盖地图/世界一致性、激光求交、碰撞、预览 A*、四种速度看门狗、暂停后旧指令不重放、参数和清单。集成测试通过实际编译的 C++ 核心驱动二维机器人，验证插队、两事件按序完成、巡逻恢复、去重、断流停车、故障解除后仍暂停。指标报表另有有限观察窗口与首次延迟统计测试。
- 本机启动了预览 HTTP 服务。Playwright Chromium 实际点击地图、发送警报、暂停/继续，检查状态与记录刷新、桌面和 430px 窄屏无横向溢出，未发现浏览器脚本错误。截图在 `docs/images/`，机器结果在 `test_results/ui_smoke.json`。
- Python 源码语法、四个包的 XML、生成 YAML/PGM/世界内容经过检查。当前任务管理程序为 `mission_manager`。

## 2026-11-02 尚未实际执行

当前工作机没有可用的 ROS2 Linux 环境，WSL 无法访问，Docker Linux 引擎未启动。因此**没有声称以下项目已经通过**：

1. ROS2 Humble 下的整工作空间 colcon 构建和接口代码生成。
2. 真实 Nav2 启动、规划/避障、取消结果链路、任务恢复和故障处理的端到端验收。
3. TurtleBot3/Gazebo 模型生成、AMCL 定位、激光与地图匹配，以及 VMware 的帧率和完整巡逻。
4. GitHub Actions 执行；工作目录尚未发布到远程仓库。

安装/构建脚本、真实 Nav2 黑盒验收脚本和 CI 工作流已经提供。复制到 Ubuntu 后运行 `bash scripts/setup_ubuntu.sh`、`bash scripts/run.sh rviz:=false panel:=false`，再在加载 ROS 环境的第二终端运行 `python3 tools/ros_acceptance.py`。失败时检查 `~/.ros/log/` 与 `~/.ros/patrol_runs/`，不要用预览通过代替真实导航验收。

## 当前实现的明确边界

事件处置是模拟计时；轻量 ROS 后端使用理想定位；本机预览使用简化 A*。没有实现跨重启恢复、真实传感器识别、多机器人、硬件急停认证或生产部署。指标来自单次仿真的有限观察窗口，不证明真实安全事件已被正确处置。Gazebo 使用 Humble 对应的 Classic 接口。

## 2026-11-11 日志与退出修复

用户提供的 Ubuntu 日志显示：`control_panel` 因覆盖 `rclpy.Node.clients` 只读属性而无法启动；行为树 100 Hz 循环多次超时；运行中按 Ctrl+C 后出现无效 ROS 上下文，以及 `controller_server` 退出码 -11。

本次修改：

- 将控制台自有客户端字典改名为 `service_clients`，保留已有 INFO/WARN 日志分级。
- 行为树循环周期改为 50 ms，动作响应超时改为 100 ms；控制器仍为 10 Hz，真实的控制循环超时警告继续显示。
- Python 节点和 C++ 任务管理器收到 SIGINT/SIGTERM 时先请求退出，完成当前回调及清理后才关闭上下文；速度保护器在有效上下文中发送最后一条零速度指令。
- `scripts/run.sh` 使用独立会话启动 launch，先调用 `patrol/prepare_shutdown` 暂停任务并等待当前导航终结，再请求 Nav2 生命周期 SHUTDOWN，最后发送退出信号。服务或进程超时会提示并退回进程退出流程，不无限等待。
- CI 入口改用同一个启动脚本；没有实际触发 GitHub Actions。

Windows 本地验证：25 项 Python 测试通过，其中新增 12 项使用 ROS 接口替身，覆盖只读属性冲突、网页命令分发、信号到达时的发布/清理顺序、退出准备等待、服务缺失、超时和 launch 返回码传递。原有预览集成测试使用现存 C++ 预览二进制；没有重新编译含 ROS 适配层的 `mission_node.cpp`。相关 Python 文件语法检查通过。

这些检查不等同于 Ubuntu/Nav2 实测。仍需在 Ubuntu 重新构建三个包，检查网页能打开、巡逻和插队可用，再在导航过程中按一次 Ctrl+C，确认无 Python 回溯、无 context invalid、无 exit code -11。20 Hz 设置能否消除全部行为树超时，也需要观察实际虚拟机负载。

退出顺序参考 [Nav2 Humble 生命周期管理器源码](https://github.com/ros-navigation/navigation2/blob/humble/nav2_lifecycle_manager/src/lifecycle_manager.cpp)；该实现按节点列表的逆序执行停用和清理。Python 上下文关闭语义参考 [rclpy Humble 初始化与关闭实现](https://github.com/ros2/rclpy/blob/humble/rclpy/rclpy/__init__.py)。

## 2026-11-11 GitHub Actions 依赖安装修复

用户提供的 Actions 截图显示，`Install and build` 在 APT 安装阶段以 100 退出：`libgoogle-glog-dev` 依赖的 `libunwind-dev` / `libunwind7-dev` 无法满足；尚未进入 C++ 编译。截图没有展开 APT 求解器输出，不能据此认定某个具体版本的软件包被锁定。

CI 改用官方 `ros:humble-ros-base-jammy` 作业容器，保留 Ubuntu 22.04 与 Humble；移除宿主机上的 `setup-ros` 安装步骤，容器内先准备原安装脚本需要的 `sudo`，后续继续运行同一份安装、编译、测试和真实 Nav2 验收流程。容器的脚本默认 shell 明确设为 Bash。

依据：[setup-ros 官方说明](https://github.com/ros-tooling/setup-ros#alternative-to-setup-ros)允许直接使用预装 ROS 的容器；[官方镜像清单](https://github.com/docker-library/official-images/blob/master/library/ros)提供该 Humble/Jammy 标签。此改动隔离宿主机预装依赖，不需要在用户的 Ubuntu 虚拟机中移除开发库。

本机已检查工作流 YAML、步骤顺序和变更内容。本机 Docker Linux 引擎未运行，没有执行容器内 APT 安装或触发远程工作流；最终结果以提交新配置后触发的新一轮 Actions 为准。

## 2026-11-12 后续开发路线与证据边界

本次只更新文档：新增 [安全性与稳定性开发路线](../设计与路线/ROS2自主巡检项目_安全性与稳定性开发路线.md)，并同步 README、原训练路线、学习笔记、设计、实验与环境说明。核对依据为当前源码、接口、参数、测试入口和 Humble 官方资料；未修改源码、未运行新的 ROS2/Nav2 验收，也未产生安全指标或通过记录。

文档检查覆盖 README 与 `docs` 下共 11 份 Markdown：44 处本地文件链接均可解析，代码块闭合，后续任务 10～19 与故障用例 F01～F15 编号完整，任务复选框保持未勾选。原任务 1～9 的功能与验收内容保持原样。

安全性与稳定性是完成原 C++ 训练任务 1～9 后的项目目标。任务 10～18为规划，任务 19 的 SROS2 为选做；本次不更改任何任务的验收状态。

| 需要区分的内容 | 当前证据与后续动作 |
|---|---|
| 已有基础保护 | 字段校验、取消屏障、期限/重试、故障锁存、门禁和顺序退出可在源码中定位；运行结论只使用对应日期的实测记录 |
| 原训练进度 | 工作区已有报警入口计数，但观察节点仍为骨架，未见排队撤销接口和反馈回调；学习笔记另有练习与输出，先核对并同步 Ubuntu 代码，不推定全部完成 |
| 新安全性目标 | 目标区域、反馈失联、连续健康恢复、完整缓存失效、STALE 与关联审计，均待逐项实现及正常/异常/回归验收 |
| 新稳定性证据 | 需保存故障复位、重复测量、导航中退出与持续运行的实际结果；目前不报告稳定运行时长、停车性能或改进百分比 |
| 可选通信安全 | 未据本次文档声明启用 SROS2；需授权/拒绝对照并限定节点与话题范围 |

进入任务 10 前冻结原任务 9 完成后的源码、配置、环境和回归结果。后续按用例记录运行后端、输入、预期、实际、PASS/FAIL/TIMEOUT/SKIP、时间起止、失败/缺失样本、证据路径与清理结果。新增安全脚本、事件格式和指标报告应在实际实现后登记，不能先用模板填“通过”。
