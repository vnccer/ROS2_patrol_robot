# ROS2 自主巡检项目：开发笔记

> 记录原则：每个任务只记四件事——**输入、处理、输出、验证要点**。具体代码细节直接回源码看，不在笔记里贴长段终端刷屏日志。

## 常用构建与测试命令（Ubuntu）

每个新终端先加载环境；修改源码后先退出旧程序，再编译重启。

```bash
cd ~/ROS2_patrol_robot
source /opt/ros/humble/setup.bash

# 首次全量编译 / 增量编译（含测试）
colcon build --symlink-install --cmake-args -DBUILD_TESTING=ON
# 只编当前包 / 连同依赖包一起编（Debug 模式供 GDB 调试）
colcon build --packages-select patrol_manager --symlink-install --cmake-args -DBUILD_TESTING=ON
colcon build --packages-up-to patrol_manager --symlink-install --cmake-args -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE=Debug
source install/setup.bash

# 运行单元测试并查看汇总
colcon test --packages-select patrol_manager --event-handlers console_direct+
colcon test-result --verbose

# 启动系统（常用模式）
bash scripts/run.sh rviz:=false
bash scripts/run.sh rviz:=false nav_log_level:=warn mission_log_level:=debug
bash scripts/run.sh backend:=gazebo gui:=false

# 端到端黑盒验收（需先在另一终端启动系统）
python3 tools/ros_acceptance.py
```

---

## 第一阶段：调度基础、旁路观察与工程闭环（任务 1～9，已完成）

### 阶段复盘

```text
报警消息 ──→ mission_manager ──→ Nav2 执行导航
                    │                 │
                    │ ←── 反馈、结果 ─┘
                    └── /patrol/status ──→ patrol_node ──→ /patrol/summary
```

- **三条调用链**：观察链路（`/patrol/status` → `patrol_node` 缓存计数 → 1 Hz `/patrol/summary`）、撤销链路（`/patrol/cancel_pending` Service → `mission_->cancel_pending()` 改队列发记录）、导航链路（Action Goal → 带 `token` 校验的 Feedback 与 Result）。
- **一个验证闭环**：核心单测（验业务规则）→ GDB（看分支与变量）→ ROS2 实机通信验证 → 黑盒回归验收（防破坏旧功能）。

| 任务 | 做了什么 | 核心能力 |
|---|---|---|
| 1～2 | 接警计数 + 提取 `on_incident()` 成员回调 | 修改已有 C++ 节点、组织回调与成员状态 |
| 3～5 | 新建 `patrol_node`：订阅状态、定时发摘要、清零服务 | 独立编写完整 ROS2 C++ 节点（Sub/Pub/Timer/Srv） |
| 6～7 | `mission.hpp` 业务撤销 + `CancelPending.srv` 接入 | 需求贯通业务核心、自定义接口与 ROS2 通信层 |
| 8 | 接入 Nav2 反馈、按 `token` 防旧回调、用 `/plan` 估距与限频 | 异步回调身份校验与日志治理 |
| 9 | GDB 调试、Launch 集成、补自动验收并跑全量回归 | 断点调试、系统集成与自动化回归 |

---

### 任务 1：报警接收计数

- **输入**：`/patrol/incidents` 上的合法、重复与非法报警消息。
- **处理**：在 [mission_node.cpp](../src/patrol_manager/src/mission_node.cpp) 报警回调入口累加 `incident_received_count_`，再执行校验与提交。
- **输出**：终端打印接收次数、ID、优先级（后续任务 8 已调为 DEBUG 级），重启后归零。
- **验证要点**：暂停后依次发合法 A、合法 B、重复 A、优先级 0 的 C，确认接收计数 +4，`/patrol/records` 出现 2 次 `accepted`、1 次 `duplicate`、1 次 `rejected`；重启后计数从 1 开始。**已通过。**

### 任务 2：提取报警成员回调

- **输入**：报警订阅回调收到的消息。
- **处理**：在 [mission_node.cpp](../src/patrol_manager/src/mission_node.cpp) 将接警逻辑抽离为 `on_incident()` 成员函数，订阅 lambda 仅做转发。
- **输出**：计数、校验、调度行为与重构前完全一致。
- **验证要点**：重复任务 1 输入行为不变；发一条新 ID 报警，确认 `/patrol/records` 依次经历 `accepted → dispatched → arrived → completed`。**已通过。**

### 任务 3：系统状态订阅

- **输入**：`/patrol/status` 上的 `MissionStatus`。
- **处理**：在 [patrol_node.cpp](../src/patrol_manager/src/patrol_node.cpp) 的 `on_status()` 累加计数、缓存最新消息，仅在状态名变化时打印。
- **输出**：状态切换（如暂停/恢复）时打印 `received` 与 `state`，同状态不刷屏。
- **验证要点**：调用 `/patrol/set_paused` 切换 `true/false`，确认只打印状态变更且接收计数持续增长（实测 212 → 2722）。**已通过。**

### 任务 4：定时摘要发布

- **输入**：缓存的最新状态、累计接收数与 1 Hz 定时器。
- **处理**：在 [patrol_node.cpp](../src/patrol_manager/src/patrol_node.cpp) 组装摘要字符串；未收到状态前输出 `NO_STATUS`。
- **输出**：每秒向 `/patrol/summary` 发布 `state=... active_id=... queue_size=... received=...`。
- **验证要点**：先单独启 `patrol_node` 确认每秒输出 `NO_STATUS`；再启主系统确认字段同步且 `ros2 topic hz /patrol/summary` 约 1 Hz；主系统退出后保持最后快照、计数停止增长。**已通过。**

### 任务 5：清零统计服务

- **输入**：`/patrol/monitor/reset_count`（`std_srvs/srv/Trigger`）请求。
- **处理**：在 [patrol_node.cpp](../src/patrol_manager/src/patrol_node.cpp) 服务回调中将 `status_received_count_` 归零，保留最近状态缓存。
- **输出**：返回 `success: true`，后续 `/patrol/summary` 从零重新累计。
- **验证要点**：运行中调用服务返回 `Status received reset.`，`/patrol/summary` 计数骤降并重新累计（实测 1131 → 9），状态字段保持不变。**已通过。**

### 任务 6：业务层实现撤销

- **输入**：待撤销的排队报警 ID。
- **处理**：在 [mission.hpp](../src/patrol_manager/include/patrol_manager/mission.hpp) 实现 `cancel_pending()`：遍历 `queue` 删除匹配项并写 `pending_cancelled` 记录，保留 `active`、剩余队列顺序和 `known` 去重历史。
- **输出**：找到并删除返回 `true`，否则返回 `false`。
- **验证要点**：在 [test_mission.cpp](../src/patrol_manager/test/test_mission.cpp) 覆盖空队列、未知 ID、中间删除、去重保留、活动任务保护、被抢占重排队等场景。实测（2026-11-14）：`mission_core` 通过（60 项业务断言全过）。**已通过。**

### 任务 7：接入自定义撤销服务

- **输入**：`/patrol/cancel_pending` 请求（`patrol_interfaces/srv/CancelPending`，含 `string id`）。
- **处理**：定义并注册 [CancelPending.srv](../src/patrol_interfaces/srv/CancelPending.srv)；在 [mission_node.cpp](../src/patrol_manager/src/mission_node.cpp) 创建服务回调调用 `mission_->cancel_pending(req->id)`。
- **输出**：撤销成功返回 `success: true` 并发布 `pending_cancelled` 记录；不在排队队列返回 `false` 且不影响活动任务。
- **验证要点**：暂停系统并提交 A/B/C（`queue_size=3`）→ 依次撤销 B、A、C，`queue_size` 依次降为 2→1→0，且每步返回 `Pending incident cancelled.`。**已通过。**

### 任务 8：Nav2 导航反馈观察与日志治理

- **输入**：Nav2 `NavigateToPose` Feedback、`/plan` 全局路径，以及派发时保存的 `task_id` 和 `token`。
- **处理**：
  - 在 `start()` 注册反馈回调，按 `token`、`flying`、`cancelling` 过滤旧目标残余回调。
  - 限频策略：报警 1 s/次、巡逻 5 s/次；清理临时调试标记，默认 Nav2 仅显 ERROR（诊断时用 `nav_log_level:=warn mission_log_level:=debug`）。
  - **首帧距离修复**（[feedback_path.hpp](../src/patrol_manager/include/patrol_manager/feedback_path.hpp)）：不采用延时跳帧，改用“本次派发后生成 + 坐标系匹配 + 终点容差 ≤ 0.5 m”的 `/plan` 与当前位置估算路径剩余距离（`source=current_plan`），未就绪前仅输出一次 `WAITING_FOR_CURRENT_PLAN`。
- **输出**：终端输出 `feedback id=... token=... remaining=... m source=current_plan`。
- **验证要点**：普通报警连续递减、暂停重派 `token` 递增且旧 `token` 不再打印、高优先级抢占切换（29→30→31）均已通过（2026-11-16）。
- **遗留小项**：`[ ]` 首帧距离修复（`source=current_plan`）代码与单测已就绪，待 Ubuntu 上实跑复测一次确认日志。

### 任务 9：GDB 调试、Launch 集成与自动验收

- **输入**：Debug 构建的 `test_mission`、统一启动脚本、端到端验收脚本。
- **处理**：
  1. 用 GDB 在 `patrol::Mission::cancel_pending` 下断点，单步观察空队列、未知 ID、以及 `queue.erase(it)` 删除中间元素 `b` 前后队列变化。
  2. 在 [system.launch.py](../src/patrol_bringup/launch/system.launch.py) 纳入 `patrol_node` 随系统自启（日志级别 `info`）。
  3. 在 [ros_acceptance.py](../tools/ros_acceptance.py) 新增 `cancel_pending()` 与 `check_pending_cancellation()`，补齐 5 项撤销验收用例，失败异常同样落盘到 `ros_acceptance.json`。
- **输出**：`ros2 node list` 包含 `/patrol_node`；`python3 tools/ros_acceptance.py` 全量回归 PASS。
- **验证要点**：15 项黑盒用例（含启动、抢占、嵌套恢复、去重、巡逻恢复、里程计超时、零速、故障锁存恢复、暂停保留及 5 项撤销保护）全部通过。**已通过。**

---

## 第二阶段：路线 C——摸透仿真 + 激光感知报警 + 自定义巡检 Action（任务 10～15，规划中）

> 阶段目标：把 `lightweight_sim` 与 `Gazebo` 两套仿真链路彻底用明白；让机器人从“人手发报警 + 到点干等”升级为“**自己用雷达发现地图外异常 → 自动上报报警 → 到达后执行可取消的巡检 Action**”。

```text
仿真投放“地图外障碍物”
      │ (/scan + TF2 + /map)
      ▼
anomaly_detector (感知节点：坐标变换 + 静态地图比对 + 防刷屏)
      │ /patrol/incidents
      ▼
mission_manager (调度层：抢占导航 → 到达后调用巡检 Action)
      ├── NavigateToPose ──→ Nav2
      └── InspectTarget  ──→ inspection_server (自定义 Action Server)
```

### 任务 10：摸透两套仿真后端 & 仿真动态投放障碍物

- **学习重点**：搞清 `lightweight`（[simulator.py](../src/patrol_sim/patrol_sim/simulator.py) + 静态 `map→odom`）与 `gazebo`（TurtleBot3 + AMCL + `use_sim_time`）的数据流、TF 树和 RViz2 观察方法。
- **输入**：一个新增的仿真控制服务（如 `/patrol/sim/set_obstacle`，传入开关与 `(x, y)` 坐标，或先做固定位置开关）。
- **处理**：
  1. 用 `ros2 run tf2_tools view_frames`、RViz2 分别观察两套后端的 `map → odom → base_link → base_scan`、`LaserScan` 与局部代价地图（Local Costmap），并顺手完成任务 8 的首帧距离复测。
  2. 复用 [geometry.py](../src/patrol_sim/patrol_sim/geometry.py) 中已预留的 `walls` 参数，在 [simulator.py](../src/patrol_sim/patrol_sim/simulator.py) 中支持动态追加/移除一个“不在静态地图 `indoor.pgm` 里的临时箱子”，让激光射线 `raycast` 和碰撞检测 `collides` 实时生效。
- **输出**：调用服务投放箱子后，仿真中出现一个“静态地图没有、但激光打得到”的物体；关闭后消失。
- **怎么验证成功**：打开 RViz2（`bash scripts/run.sh`），投放箱子后能看到激光红点打到箱子表面、Nav2 局部代价地图将其标为障碍并自动绕行；移除后激光穿透恢复原状。

### 任务 11：TF2 坐标变换与激光异常检测节点（只感知，不发报警）

- **学习重点**：`tf2_ros::Buffer` / `TransformListener`、`sensor_msgs/LaserScan` 极坐标转笛卡尔坐标、`nav_msgs/OccupancyGrid`（注意 `/map` 的 `TransientLocal` QoS）。
- **输入**：`/scan`（`base_scan` 坐标系）、`/map`（`map` 坐标系静态栅格图）与 TF 变换树。
- **处理**：新建 C++ 节点 `anomaly_detector`（纯算法部分照旧抽成独立 `.hpp` 方便写单测），把有效激光点转到 `map` 坐标系并换算为栅格索引；若该栅格及其周围安全邻域在静态 `/map` 中均为空闲，则判定为“地图外异常点”，聚簇求中心点坐标。
- **输出**：检测到地图外物体时，限频打印异常物体在 `map` 下的 `(x, y)` 坐标与命中点数；正常扫描已知墙体时不误报。
- **怎么验证成功**：先写纯 C++ 算法单测（给定模拟栅格与点集，验证墙边点不误报、空地异常点命中）；再启动仿真，未投放箱子巡逻一圈零误报，投放箱子后经过视野时准确打印箱子坐标（误差 < 0.3 m）。

### 任务 12：感知联动调度——自动上报报警与防刷屏

- **学习重点**：感知到决策的闭环、时序确认（防单帧噪点）与空间冷却去重、安全观察点计算。
- **输入**：任务 11 识别出的异常物体中心 `(x, y)` 与机器人当前位姿。
- **处理**：
  1. 连续命中 N 帧（如 3 帧）才确认是真异常，避免偶发噪点。
  2. 计算一个距离异常物约 0.8 m、且位于空闲区域的观察点作为导航目标（避免直接把目标设在箱子内部导致 Nav2 规划失败）。
  3. 同一空间半径内（如 1.0 m）冷却期内不重复生成新 ID；满足条件时往 `/patrol/incidents` 发布 `Incident`。
- **输出**：自动向 `/patrol/incidents` 注入报警，驱动 `mission_manager` 抢占当前巡逻并前往查看。
- **怎么验证成功**：巡逻中调用服务投放箱子，全程**不手敲 `ros2 topic pub`**，观察系统自动经历 `accepted → dispatched → arrived → completed`，且同一箱子在冷却期内不会刷爆任务队列。

### 任务 13：自定义 Action 服务端——实现可取消的巡检动作

- **学习重点**：编写自定义 `.action` 接口、`rclcpp_action::Server` 完整生命周期（`handle_goal` / `handle_cancel` / `handle_accepted` + 后台执行线程或定时器）。
- **输入**：在 `patrol_interfaces` 新增 `action/InspectTarget.action`（Goal：`task_id`, `duration_sec`；Feedback：`progress`, `stage`；Result：`success`, `summary`）。
- **处理**：新建节点 `inspection_server`，收到 Goal 后分阶段执行模拟巡检（如“定位对准 → 360° 扫描采样 → 生成摘要”），周期性发布进度 Feedback；收到 Cancel 请求时立刻中断并返回 `CANCELED`。
- **输出**：完整支持执行、进度反馈与中途取消的 ROS2 Action 服务（如 `/patrol/inspect_target`）。
- **怎么验证成功**：不启动主调度，仅启动 `inspection_server`，用命令行 `ros2 action send_goal --feedback /patrol/inspect_target ...` 验证完整跑完（0%→100%）；再发一次并在中途按 `Ctrl+C` 验证服务端正确响应取消并清理状态。

### 任务 14：调度器接入 `InspectTarget` Action 与回归验收

- **学习重点**：双 Action 状态机协同（先 `NavigateToPose`，到达后再 `InspectTarget`）、取消屏障扩展到检查阶段、端到端自动验收。
- **输入**：`mission_manager` 导航到达事件、`InspectTarget` Feedback/Result，以及检查中途的高优先级抢占或暂停请求。
- **处理**：
  1. 改造 [mission.hpp](../src/patrol_manager/include/patrol_manager/mission.hpp) 与 [mission_node.cpp](../src/patrol_manager/src/mission_node.cpp)：到达报警点进入 `HANDLING_EVENT` 时发起 `InspectTarget` Action（带 `token` 校验防旧回调），代替单纯计时等待。
  2. 若检查中途收到暂停或更高优先级报警，必须先取消 `InspectTarget` 并等待其终结，再切换下一任务。
  3. 将 `anomaly_detector` 和 `inspection_server` 接入 [system.launch.py](../src/patrol_bringup/launch/system.launch.py)，并在 [ros_acceptance.py](../tools/ros_acceptance.py) 补上“投放障碍物 → 自动报警 → 到点执行巡检 Action → 抢占取消”的自动验收用例。
- **输出**：一条完整的“感知 → 导航 → 检查 → 抢占保护”闭环系统与自动化验收报告。
- **怎么验证成功**：单元测试 + `python3 tools/ros_acceptance.py` 全量通过（原有 15 项不退化 + 新增感知与巡检 Action 用例全过）。

### 任务 15（进阶选做）：切到 Gazebo 后端跨仿真验证

- **学习重点**：真正理解仿真解耦的价值——同一套上层算法在物理引擎 + AMCL 真实定位噪声下的表现与调参。
- **输入**：`bash scripts/run.sh backend:=gazebo gui:=true`，并在 Gazebo 中插入一个方块模型作为临时障碍物。
- **处理**：不改上层业务逻辑，观察 AMCL 粒子滤波定位抖动对任务 11 异常检测邻域半径参数的影响，把敏感阈值抽成 ROS2 参数写入配置文件。
- **输出**：同一套感知报警与巡检 Action 链路在轻量仿真和 Gazebo 两种后端均可跑通。
- **怎么验证成功**：Gazebo 界面中放入箱子，TurtleBot3 巡逻路过时能识别并自动靠近执行巡检，且无持续墙体误报。
