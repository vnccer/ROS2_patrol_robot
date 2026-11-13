# ROS2 自主巡检项目：开发笔记

这份笔记只记任务思路、源码入口和操作验证命令；具体实现直接打开源码看注释。

源码入口：[任务通信层 mission_node.cpp](../../src/patrol_manager/src/mission_node.cpp)、[业务核心 mission.hpp](../../src/patrol_manager/include/patrol_manager/mission.hpp)、[练习节点 patrol_node.cpp](../../src/patrol_manager/src/patrol_node.cpp)。构建配置见 [CMakeLists.txt](../../src/patrol_manager/CMakeLists.txt)。

## 0. 通用操作

**每个新终端先执行：**

```bash
cd ~/ROS2_patrol_robot
source /opt/ros/humble/setup.bash
source install/setup.bash
```

**修改后：**先退出旧进程，再编译、重新加载环境、重启。仅修改 `patrol_manager` 时：

```bash
colcon build --packages-select patrol_manager --symlink-install
source install/setup.bash
```

需要同时构建工作区内的依赖包时，将上面的 `--packages-select` 改成 `--packages-up-to`。

**终端 A：启动主系统。** 按一次 `Ctrl+C`，等待正常退出。

```bash
bash scripts/run.sh rviz:=false
```

**终端 B：任务 3～4 另行启动练习节点。**

```bash
ros2 run patrol_manager patrol_node
```

终端 C、D 用于下面的操作与观察。`echo`、`hz` 会持续运行，按 `Ctrl+C` 结束；`echo --once` 只看一条。

## 1. 观察正常巡逻

思路：列出节点和通信接口，再看任务状态。Topic 持续传消息，Service 请求一次返回一次，Action 处理持续一段时间的导航任务。

```bash
ros2 node list
ros2 topic list -t
ros2 service list -t
ros2 action list -t
ros2 topic echo /patrol/status --once
ros2 topic hz /patrol/status
```

看 `state`、`active_id`、`queue_size`、`paused`、`motion_permitted`。正常巡逻时状态会切换，`/patrol/status` 默认约 20 Hz。

## 2. 基础通信与调度练习

### 2.1 Topic 接警与 Action 导航

思路：报警消息进入订阅回调，校验并转换成任务；业务层接收、调度，通信层调用 Nav2，最终记录到达与完成。

源码入口：`mission_node.cpp` 的 `on_incident()`、`start()`、`result_callback`；`mission.hpp` 的 `submit()`、`tick()`、`result()`。

终端 C：先观察任务记录。

```bash
ros2 topic echo /patrol/records
```

终端 D：查看 Action 连接，再发送报警。同一管理器进程内 ID 去重，每次实验使用新 ID。

```bash
ros2 action info /navigate_to_pose
ros2 interface show nav2_msgs/action/NavigateToPose

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: action-$(date +%s), priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"
```

预期：Action 客户端中有 `/mission_manager`；同一报警依次出现 `accepted → dispatched → arrived → completed`，到达后约 3 秒完成处置。`accepted` 只代表接收，不代表已经导航。

### 2.2 Service 暂停与继续

思路：服务回调修改业务层暂停状态；暂停时取消当前导航，继续时等待旧导航终结后重新调度。

源码入口：`mission_node.cpp` 中搜索 `patrol/set_paused`；`mission.hpp` 的 `pause()`、`suspend()`。

```bash
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'
ros2 topic echo /patrol/status --once

# 观察暂停后，再继续
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'
ros2 topic echo /patrol/status --once
```

预期：`paused` 随请求切换，暂停时运动许可关闭。服务返回成功只表示请求已处理，导航取消结果继续看状态和记录。

### 2.3 Timer 周期验证

思路：任务管理器每 50 ms 调用一次 `tick()`。临时改成 100 ms，编译重启后比较状态发布频率，最后恢复 50 ms 并再次编译重启。

源码入口：`mission_node.cpp` 中搜索 `create_wall_timer`。

修改前、修改后分别在独立终端观察：

```bash
ros2 topic hz /patrol/status
```

每次改动后，在主系统终端执行：

```bash
colcon build --packages-select patrol_manager --symlink-install
source install/setup.bash
bash scripts/run.sh rviz:=false
```

预期：50 ms 时约 20 Hz，100 ms 时约 10 Hz。原练习已观察到约 20.006 Hz 和 10.005 Hz。

### 2.4 报警优先级与排队 TTL

思路：先暂停，依次提交低、高优先级报警，再继续；通过派发顺序验证优先级，而不是只看消息发送顺序。

源码入口：`mission.hpp` 的 `submit()`、`best()`、`tick()`。

终端 C：

```bash
ros2 topic echo /patrol/records
```

终端 D：以下命令在同一终端依次执行，并在 180 秒内继续运行。

```bash
run_id="priority-$(date +%s)"
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-low, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-high, priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"

ros2 topic echo /patrol/status --once
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'
```

预期：本次高优先级报警先派发并完成，再执行低优先级报警。原练习已验证；也遇到过暂停太久导致两个报警 `expired / pending TTL`，因此过期不能误判为优先级调度失败。

### 2.5 整体调用链回忆

思路：接警 → 校验和入队 → 定时调度 → Nav2 导航 → 到达后处置 → 完成并继续巡逻。对照 2.1 的记录和 2.2 的暂停操作回看源码即可。

## 3. C++ 开发任务

### 任务 1：报警接收计数

思路：计数保存在节点成员中，每次进入报警回调先加一，再做校验；重复和拒绝消息也计数，进程重启后从零开始。

源码入口：`mission_node.cpp` 的 `incident_received_count_`、`on_incident()`。按第 0 节编译并重启主系统，主系统终端观察 `received=...` 日志。

终端 C：

```bash
ros2 topic echo /patrol/records
```

终端 D：同一终端依次发送合法 A、合法 B、重复 A、非法 C。

```bash
run_id="count-$(date +%s)"
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-a, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-b, priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-a, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"

ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-c, priority: 0, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"

ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'
```

预期：接收计数增加 4；本次输入对应两次 `accepted`、一次 `duplicate`、一次 `rejected`。重启主系统后再发消息，接收计数从 1 开始。

### 任务 2：提取报警成员回调

思路：把报警处理移入 `on_incident()`，订阅 Lambda 只负责转发消息，计数、校验和业务行为保持一致。

源码入口：`mission_node.cpp` 的 `incidents_`、`on_incident()`。

验证：按第 0 节编译重启，重复任务 1 的四条输入；再执行 2.1 的单条报警验证，确认仍有完整的接收、派发、到达和完成记录。

### 任务 3：独立实现状态订阅

思路：`patrol_node` 订阅 `/patrol/status`，每条消息更新计数和完整缓存，只在状态名变化时打印日志；在 CMake 中配置编译、依赖和安装。

源码入口：`patrol_node.cpp` 的 `on_status()`、`last_state_`、`last_status_`、`status_received_count_`；`CMakeLists.txt` 的 `patrol_node` 目标。

按第 0 节编译，分别启动主系统和练习节点。终端 C：

```bash
ros2 node info /patrol_node
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'

# 保持暂停几秒，再继续
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'
```

预期：练习节点打印 `PAUSED` 和继续后的状态，状态不变时不反复打印，但接收计数持续增加。原练习记录中，暂停前后计数从 212 增至 2722，符合预期。

### 任务 4：增加定时摘要发布

思路：订阅回调更新缓存和计数；独立定时器每秒读取缓存，向 `/patrol/summary` 发布 `std_msgs/msg/String`，包含状态、任务 ID、队列长度和接收计数。首次收到状态前发布 `NO_STATUS`。

源码入口：在 `patrol_node.cpp` 增加发布器、定时器、收到消息标志和 `publish_summary()`；给 `CMakeLists.txt` 的练习节点补充 `std_msgs` 依赖，沿用 `package.xml` 已有依赖。当前工作区尚未加入这些实现。

按第 0 节编译，**先只启动练习节点**。终端 C：

```bash
ros2 topic echo /patrol/summary
```

预期：每秒收到 `NO_STATUS`。随后在终端 A 启动主系统：

```bash
bash scripts/run.sh rviz:=false
```

预期：摘要改为最近状态和统计值。终端 D 分别检查频率和原始状态：

```bash
ros2 topic hz /patrol/summary
# 观察频率后按 Ctrl+C，再执行
ros2 topic echo /patrol/status --once
```

预期：摘要约 1 Hz，字段与最近状态对应；接收计数统计状态消息，不是摘要条数。主系统停止后仍发布最后的快照，计数停止增长；超时判断留作后续任务。

### 任务 5：增加清零统计的 Service

思路：



## 4. 后续入口

任务 5～9 按 [C++ 实践训练路线](../设计与路线/ROS2自主巡检项目_C++实践训练路线.md) 继续；完成后再进入 [安全性与稳定性开发路线](../设计与路线/ROS2自主巡检项目_安全性与稳定性开发路线.md)。每做完一个任务，只补一段思路、源码入口和验证命令。
