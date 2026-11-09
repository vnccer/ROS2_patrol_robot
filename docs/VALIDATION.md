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
