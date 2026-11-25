# ROS2 移动机器人自主巡检与事件响应系统

基于 **Ubuntu 22.04 + ROS2 Humble + C++17 + Nav2** 的移动机器人巡检与任务调度系统，围绕「核心任务调度 → 仿真验证（轻量仿真 / Gazebo）→ 树莓派真机迁移」设计。

## 1. 系统架构与核心能力

```text
ROS2 Topic / Service (/patrol/incidents, /patrol/set_paused, /patrol/cancel_pending ...)
          │
          ▼
mission_manager (C++17: 状态机 / 优先队列 / 取消屏障 / 恢复 / 审计日志)
    ├── /patrol/status ──▶ patrol_node (C++17: 状态观察 / 定时摘要 / 统计清零)
    └── NavigateToPose Action ──▶ Nav2 (全局规划 / 局部控制 / 恢复行为)
                                      │ /nav_cmd_vel
                                      ▼
                                velocity_guard (运动许可 + 传感器/指令新鲜度看门狗)
                                      │ /cmd_vel (唯一速度出口)
                                      ▼
                        轻量底盘仿真 / Gazebo TurtleBot3 / (后续) 树莓派真机底盘
                                      │ /odom, /scan, TF
                                      ▼
                                Nav2 + mission_manager + RViz2
```

- **解耦的 C++17 核心调度（`mission.hpp`）**：与 ROS2 通信层解耦，可直接独立单元测试；支持多点循环巡逻、事件优先级抢占（1～100，同级 FIFO）、嵌套抢占、显式取消屏障（等待旧 Action 终结再派发）、递增 token 防旧回调污染、巡逻点断点恢复、进程内 ID 去重、队列 TTL 过期、排队报警撤销、有限重试与故障锁存。
- **导航进度估算（`feedback_path.hpp`）**：基于当前目标派发后匹配坐标系与终点的 `/plan` 估算剩余路径长度，避免目标切换首帧读取旧路径残留距离。
- **状态观察节点（`patrol_node.cpp`）**：订阅 `/patrol/status` 监控状态变化，定时发布 `/patrol/summary` 摘要，并提供 `/patrol/monitor/reset_count` 清零服务。
- **运动安全看门狗（`velocity_guard`）**：统一接管 `/cmd_vel` 出口，持续校验运动许可、速度指令、里程计和激光数据新鲜度，任一超时自动输出零速度，仿真与真机均可复用。
- **可切换运行后端**：默认轻量二维差速/激光仿真（适合虚拟机流畅跑真实 Nav2），可选 Gazebo Classic + TurtleBot3 Burger + AMCL，后续接入树莓派 ROS2 小车时仅需替换底盘/传感器驱动与建图配置。

## 2. 目录结构

```text
ROS2_patrol_robot/
├── src/
│   ├── patrol_interfaces/   # 自定义 ROS2 消息与服务 (Incident / MissionStatus / TaskRecord / CancelPending)
│   ├── patrol_manager/      # 核心 C++17 节点 (mission_manager, patrol_node) 与核心单元测试
│   ├── patrol_sim/          # 轻量 2D 仿真底盘 (lightweight_sim) 与速度看门狗 (velocity_guard)
│   └── patrol_bringup/      # 统一 launch、Nav2/任务参数、室内地图、Gazebo 世界、URDF 与 RViz 配置
├── scripts/
│   ├── setup_ubuntu.sh      # Ubuntu 22.04 依赖安装、编译与 C++ 单元测试
│   ├── run.sh               # 统一启动入口（含 Ctrl+C 优雅停止 Nav2 生命周期）
│   └── run_system.py        # 启动与有序退出监管脚本
├── tools/
│   └── ros_acceptance.py    # 真实 ROS2 + Nav2 黑盒端到端验收脚本
├── docs/                    # 个人环境配置、Git 与开发笔记
└── .github/workflows/ci.yml # ROS2 Humble 自动构建、单元测试与黑盒验收 CI
```

## 3. ROS2 核心接口

| 类型 | 名称 | 说明 |
|---|---|---|
| Topic (`patrol_interfaces/msg/Incident`) | `/patrol/incidents` | 注入报警事件（`map` 坐标系、归一化四元数，ID 不得以 `patrol/` 开头） |
| Topic (`patrol_interfaces/msg/MissionStatus`) | `/patrol/status` | 发布任务状态、当前任务 ID/优先级、队列长度、完成计数与故障 |
| Topic (`patrol_interfaces/msg/TaskRecord`) | `/patrol/records` | 发布任务审计事件（同时写入 `~/.ros/patrol_runs/<run>/records.csv`） |
| Topic (`std_msgs/msg/String`) | `/patrol/summary` | `patrol_node` 每秒发布一次的状态摘要 |
| Topic (`std_msgs/msg/Bool`) | `/patrol/motion_permit` | 心跳式运动许可，驱动 `velocity_guard` 放行或停车 |
| Action (`nav2_msgs/action/NavigateToPose`) | `/navigate_to_pose` | 发送/取消 Nav2 导航目标并接收反馈与结果 |
| Service (`std_srvs/srv/SetBool`) | `/patrol/set_paused` | 暂停 / 恢复巡检任务 |
| Service (`patrol_interfaces/srv/CancelPending`) | `/patrol/cancel_pending` | 按 ID 撤销等待队列中的报警任务 |
| Service (`std_srvs/srv/Trigger`) | `/patrol/emergency_stop` | 触发急停并锁存故障 |
| Service (`std_srvs/srv/Trigger`) | `/patrol/recover` | 传感器与 Nav2 恢复健康后解除故障 |
| Service (`std_srvs/srv/Trigger`) | `/patrol/prepare_shutdown` | 暂停并确认旧导航终结，供退出流程安全关闭 Nav2 |
| Service (`std_srvs/srv/Trigger`) | `/patrol/monitor/reset_count` | 清零 `patrol_node` 的状态消息接收计数 |
| Service (`std_srvs/srv/SetBool`) | `/patrol/sim/{drop_odom,drop_scan,blocked}` | 轻量仿真故障注入开关 |

## 4. 快速开始（Ubuntu 22.04 + ROS2 Humble）

### 4.1 安装依赖并编译

先完成 ROS2 Humble 基础环境安装（见 [docs/ROS2环境配置humble.md](docs/ROS2环境配置humble.md)），随后在工作空间根目录执行：

```bash
bash scripts/setup_ubuntu.sh
# 如需 Gazebo + TurtleBot3 仿真，增加 --gazebo 参数
# bash scripts/setup_ubuntu.sh --gazebo
```

日常修改源码后增量编译：

```bash
source /opt/ros/humble/setup.bash
colcon build --symlink-install --cmake-args -DBUILD_TESTING=ON
source install/setup.bash
```

### 4.2 启动仿真

```bash
# 默认：真实 Nav2 + 轻量底盘仿真 + RViz2
bash scripts/run.sh

# 虚拟机低负载模式（关闭 RViz2）
bash scripts/run.sh rviz:=false

# 调试日志模式（查看 Nav2 警告与任务管理器 DEBUG 日志）
bash scripts/run.sh rviz:=false nav_log_level:=warn mission_log_level:=debug

# Gazebo Classic + TurtleBot3 Burger + AMCL 模式
bash scripts/run.sh backend:=gazebo gui:=false
```

按一次 `Ctrl+C` 退出：`scripts/run.sh` 会先暂停任务、等待当前导航终结，再通过生命周期管理器关闭 Nav2。

### 4.3 命令行操控与观察

在新的 Ubuntu 终端加载环境后运行：

```bash
source /opt/ros/humble/setup.bash
source install/setup.bash

# 发送报警事件（优先级 1~100，越大越优先）
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
  '{id: alarm-001, priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 6.5, y: 6.5}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}'

# 暂停 / 恢复 / 撤销排队报警
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'
ros2 service call /patrol/cancel_pending patrol_interfaces/srv/CancelPending '{id: alarm-001}'
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'

# 查看状态、任务记录与观察节点摘要
ros2 topic echo /patrol/status
ros2 topic echo /patrol/records
ros2 topic echo /patrol/summary
```

### 4.4 单元测试与黑盒验收

```bash
# 1. C++ 核心单元测试（mission_core + feedback_path）
colcon test --packages-select patrol_manager --event-handlers console_direct+
colcon test-result --verbose

# 2. 真实 Nav2 端到端黑盒验收（终端 1 先运行 bash scripts/run.sh rviz:=false）
python3 tools/ros_acceptance.py
```

## 5. 后续树莓派真机迁移规划

当前上层调度（`patrol_manager`）、自定义接口（`patrol_interfaces`）和速度安全门禁（`velocity_guard`）已与底层仿真解耦。后续接入树莓派 + ROS2 小车真机时：

1. 在 `patrol_bringup` 中新增真机 launch，关闭 `lightweight_sim` 与静态 `map -> odom`，接入真实底盘驱动、雷达驱动与 SLAM/AMCL 定位；
2. 根据真实车体尺寸、限速与传感器参数微调 `config/nav2.yaml` 与 `config/mission.yaml`；
3. 复用 `velocity_guard` 接管 `/nav_cmd_vel -> /cmd_vel` 并校验底盘硬件断流停机保护。

## 6. 个人学习与开发文档

- [ROS2 环境配置（Humble）](docs/ROS2环境配置humble.md)
- [Git 使用指南](docs/git指南.md)
- [ROS2 自主巡检项目开发笔记](docs/ROS2自主巡检项目_开发笔记.md)
