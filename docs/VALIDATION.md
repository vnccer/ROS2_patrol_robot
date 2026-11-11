# 验证记录

日期：2026-11-02。当前工作机为 Windows，项目目标运行环境为 Ubuntu 22.04 + ROS2 Humble。

## 本机实际执行

- 用 Zig 0.16.0 的 C++17 编译器编译了共享任务核心和预览桥接程序，运行通过 39 项任务不变量检查：巡逻索引、严格优先级、取消屏障、旧 token、同级 FIFO、嵌套恢复、去重、TTL、暂停/故障独立、取消超时、重试和队列/ID 历史上限。
- 13 项 Python 测试全部通过，覆盖地图/世界一致性、激光求交、碰撞、预览 A*、四种速度看门狗、暂停后旧指令不重放、参数和清单。集成测试通过实际编译的 C++ 核心驱动二维机器人，验证插队、两事件按序完成、巡逻恢复、去重、断流停车、故障解除后仍暂停。指标报表另有有限观察窗口与首次延迟统计测试。
- 本机启动了预览 HTTP 服务。Playwright Chromium 实际点击地图、发送警报、暂停/继续，检查状态与记录刷新、桌面和 430px 窄屏无横向溢出，未发现浏览器脚本错误。截图在 `docs/images/`，机器结果在 `test_results/ui_smoke.json`。
- Python 源码语法、四个包的 XML、生成 YAML/PGM/世界内容经过检查。当前任务管理程序为 `mission_manager`。

## 尚未实际执行

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
