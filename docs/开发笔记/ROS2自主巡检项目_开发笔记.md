# ROS2 自主巡检项目：开发笔记

一个任务只记四件事：输入、处理、输出、怎么验证成功。具体实现直接回源码看。

以下命令在 Ubuntu 执行，工程路径按实际位置替换。每个新终端先加载环境；修改源码后先退出旧程序，再编译并重启。

```bash
cd ~/ROS2_patrol_robot
source /opt/ros/humble/setup.bash
source install/setup.bash

# 修改源码后执行
colcon xxx
source install/setup.bash
```

colcon使用：
```bash
colcon build [选择哪些包] --symlink-install [额外构建设置]

# 第一次编译整个项目（刚刚clone项目时）
colcon build --symlink-install

# 依赖的构建结果已经可用，只编当前包
colcon build --packages-select patrol_manager --symlink-install

# 依赖也要一起构建或更新
colcon build --packages-up-to patrol_manger --symlink-install

# 同时修改了任务代码和启动配置
colcon build --packages-up-to patrol_manger patrol_bringup --sumlink-install
```

- `--packages-select`：只选择你写出的包。
- `--packages-up-to`：选择你写出的包，以及它们依赖的包

额外设置：

```
# 把测试程序编译出来
--cmake-args -DBUILD_TESTING=ON

# 方便 GDB 下断点、查看变量
--cmake-args -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE=Debug

# 真正运行你写的检查
colcon test --packages-select patrol_manager

# 汇总已有结果，不会再测试一遍
colcon test-result --verbose
```

## 任务 1：报警接收计数

**输入：** `/patrol/incidents` 上的报警消息，包括合法、重复和非法消息。

**处理：** 在 [mission_node.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/src/mission_node.cpp) 的报警回调入口累加 `incident_received_count_`，再做校验和提交。

**输出：** 主系统终端打印接收次数、报警 ID、优先级；每收到一条消息计数加一，进程重启后从零开始。

**怎么验证成功：** 编译后，终端 A 启动主系统，终端 B 观察任务记录。

```bash
# 终端 A
bash scripts/run.sh rviz:=false

# 终端 B（持续观察，Ctrl+C 结束）
ros2 topic echo /patrol/records
```

终端 C：在同一终端依次发送合法 A、合法 B、重复 A、优先级为 0 的 C。

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

通过标准：终端 A 的接收计数增加 4；终端 B 中本次输入对应两次 `accepted`、一次 `duplicate`、一次 `rejected`。重启主系统再发消息，接收计数从 1 开始。

## 任务 2：提取报警成员回调

**输入：** 订阅回调收到的一条报警消息。

**处理：** 在 [mission_node.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/src/mission_node.cpp) 中将处理代码移入 `on_incident()`，订阅处只调用它。

**输出：** 报警接收、计数、校验和执行行为与提取前一致。

**怎么验证成功：** 编译重启主系统后，重复任务 1 的四条输入，检查计数和记录保持一致；再发送一条新报警检查完整执行。

```bash
# 终端 B：先持续观察
ros2 topic echo /patrol/records
```

```bash
# 终端 C：发送新 ID 的报警
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: callback-$(date +%s), priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}"
```

通过标准：同一新报警依次出现 `accepted → dispatched → arrived → completed`。每次重做使用新 ID，避免被去重。

## 任务 3：系统状态订阅

**输入：** `/patrol/status` 上的 `MissionStatus` 消息。（相当于抄下公文通通知）

**处理：** 在 [patrol_node.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/src/patrol_node.cpp) 的 `on_status()` 中累加计数、保存最新消息，并比较状态名是否变化。

**输出：** 练习节点终端只在状态名变化时打印 `received` 和 `state`；每条消息都计数。

**怎么验证成功：** 编译后，分别启动主系统和练习节点，再暂停、继续。

```bash
# 终端 A
bash scripts/run.sh rviz:=false

# 终端 B
ros2 run patrol_manager patrol_node
```

```bash
# 终端 C：暂停后观察几秒，再执行继续
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'
```

通过标准：终端 B 打印 `PAUSED` 和继续后的状态；暂停期间不重复打印同一状态，继续后的接收计数明显增加。原记录：计数从 212 增至 2722，符合预期。

## 任务 4：定时摘要发布

**输入：** 最新缓存的状态消息、累计接收数，以及每秒一次的定时触发。（相当于把公文通通知挑几个重点，建小群再发消息）

**处理：** 在 [patrol_node.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/src/patrol_node.cpp) 中构造摘要；未收到过状态时使用 `NO_STATUS`，收到后读取缓存字段。

**输出：** 每秒向 `/patrol/summary` 发布一条字符串，包含状态、任务 ID、队列长度和接收计数。

**怎么验证成功：** 待补实际结果。实现并编译后，先退出主系统，只启动练习节点。

```bash
# 终端 B
ros2 run patrol_manager patrol_node

# 终端 C：持续观察
ros2 topic echo /patrol/summary
```

先确认每秒出现 `NO_STATUS`，再在终端 A 启动主系统。

```bash
# 终端 A
bash scripts/run.sh rviz:=false

# 终端 D：观察频率后按 Ctrl+C，再查看原始状态
ros2 topic hz /patrol/summary
ros2 topic echo /patrol/status --once
```

通过标准：收到状态后摘要内容更新，字段与最近状态对应，频率约 1 Hz。主系统退出后仍发布最后快照，接收计数停止增长。

## 任务 5：清零统计服务

**输入：** 对 `/patrol/monitor/reset_count` 的 `std_srvs/srv/Trigger` 请求。

**处理：** 在 [patrol_node.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/src/patrol_node.cpp) 的服务回调中清零自己的接收计数，保留最近缓存的状态。

**输出：** 服务返回成功标志和说明；后续摘要中的接收计数重新累计。

**怎么验证成功：** 待补实际结果。实现并编译后，运行主系统和练习节点，终端 C 持续观察摘要，终端 D 调用服务。

```bash
# 终端 A
bash scripts/run.sh rviz:=false

# 终端 B
ros2 run patrol_manager patrol_node

# 终端 C
ros2 topic echo /patrol/summary
```

```bash
# 终端 D：先记下当前计数，再调用；重复调用也应成功
ros2 service call /patrol/monitor/reset_count std_srvs/srv/Trigger '{}'
```

通过标准：返回 `success: true`，摘要计数从清零后重新累计，状态缓存保留。状态消息持续到达时，下一条摘要的计数可能已经大于 0。

```BASH
# 终端A
[mission_manager-12] [INFO] [1794626542.528933603] [mission_manager]: dispatched patrol/0 
[bt_navigator-9] [WARN] [1794626557.652431372] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[controller_server-5] [WARN] [1794626557.805544957] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[bt_navigator-9] [WARN] [1794626557.810058615] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[mission_manager-12] [INFO] [1794626569.828266061] [mission_manager]: arrived patrol/0 

# 终端B
[INFO] [1794626514.832433772] [patrol_node]: received=1126 state=PATROLLING
[INFO] [1794626541.478947265] [patrol_node]: received=517 state=DWELLING

# 终端C
data: state=PATROLLING active_id=patrol/3 queue_size=0 received=1131
---
data: state=PATROLLING active_id=patrol/3 queue_size=0 received=9
---

# 终端D
ros2 service call /patrol/monitor/reset_count std_srvs/srv/Trigger '{}'
requester: making request: std_srvs.srv.Trigger_Request()

response:
std_srvs.srv.Trigger_Response(success=True, message='Status received reset.')
```

## 任务 6：业务层实现撤销

**输入：** 要撤销的排队报警 ID。

**处理：** 在 [mission.hpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/include/patrol_manager/mission.hpp) 的 `cancel_pending()` 中遍历 `queue`，找到后删除并记录 `pending_cancelled`；保留 `active`、其他任务顺序及 `known` 去重历史。

**输出：** 删除成功返回 `true`，找不到返回 `false`；撤销记录携带对应报警 ID。

**怎么验证成功：** 在 [test_mission.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/test/test_mission.cpp) 中直接调用业务函数，覆盖空队列、未知 ID、中间删除、记录与去重、剩余任务顺序、活动任务保护及被抢占后重新排队的报警。测试通过传入时间模拟调度，无需启动 Nav2。

```bash
colcon build --packages-select patrol_manager --symlink-install \
  --cmake-args -DBUILD_TESTING=ON
colcon test --packages-select patrol_manager --event-handlers console_direct+
colcon test-result --verbose
```

**实测结果（2026-11-14，Ubuntu 终端记录）：** 构建成功；`mission_core` 通过，耗时 0.03 秒。

```text
PASS: 60 mission invariants
100% tests passed, 0 tests failed out of 1
Summary: 1 test, 0 errors, 0 failures, 0 skipped
```

这里是 1 个测试程序内的 60 次检查，不是 60 个独立测试；本次验证业务层规则，ROS2 服务调用留到任务 7。构建时有同名 underlay 包覆盖警告，本次仍构建成功。

## 任务 7：接入自定义撤销服务

**总体关系：** 任务 1～2 修改主管理节点的接警逻辑，任务 3～5 编写旁路状态观察节点；任务 6 实现撤销规则，任务 7 接入 ROS2 服务。最终调用链：终端请求 → `mission_node.cpp` 服务回调（任务 7）→ `mission.hpp` 的 `cancel_pending()`（任务 6）→ 返回结果。
因此本次的功能是：让外部终端通过一个ROS2服务，请求任务管理器撤销某个排队报警，并获得操作结果。

**输入：** 对 `/patrol/cancel_pending` 的自定义服务请求，携带待撤销报警的 `id`。

**处理：** 在接口包定义并注册 `CancelPending.srv`（请求 `string id`，响应 `bool success`、`string message`）；在 [mission_node.cpp](D:/4work/3project/ROS2_patrol_robot/src/patrol_manager/src/mission_node.cpp) 创建服务，回调调用任务 6 的 `cancel_pending()`，队列删除和记录仍由业务层负责。

**输出：** 排队报警撤销成功时返回 `success: true`，发布对应的 `pending_cancelled` 记录；ID 不在等待队列中时返回 `false`，活动任务保持原样。

**怎么验证成功：** 终端 B 持续执行 `ros2 topic echo /patrol/records`，其他操作在同一操作终端执行，保留 `run_id`。

### 1. 检查接口、构建并运行核心测试

```text
# /src/patorl_interfaces/srv/CancelPending.srv 指定了内容，CMakLists中写明了srv/CancelPending.srv
donk@ubuntu:~/ROS2_patrol_robot$ ros2 interface show patrol_interfaces/srv/CancelPending
string id
---
bool success
string message

# colcon编译patrol_manager，这里也启动BUILD_TESTING
donk@ubuntu:~/ROS2_patrol_robot$ colcon build --packages-up-to patrol_manager --symlink-install --cmake-args -DBUILD_TESTING=ON
Summary: 2 packages finished [29.3s]

donk@ubuntu:~/ROS2_patrol_robot$ source install/setup.bash

# 运行patrol_manager包中的测试，并把执行输出直接显示在终端
donk@ubuntu:~/ROS2_patrol_robot$ colcon test --packages-select patrol_manager --event-handlers console_direct+
1: Test command: /home/donk/ROS2_patrol_robot/build/patrol_manager/test_mission
1: Test timeout computed to be: 1500
1: PASS: 60 mission invariants
1/1 Test #1: mission_core .....................   Passed    0.00 sec
100% tests passed, 0 tests failed out of 1
Total Test time (real) =   0.01 sec
Finished <<< patrol_manager [0.09s]
Summary: 1 package finished [0.35s]


donk@ubuntu:~/ROS2_patrol_robot$ colcon test-result --verbose
Summary: 1 test, 0 errors, 0 failures, 0 skipped
```

结果：接口字段正确，两个包构建成功；有 underlay 覆盖警告。`mission_core` 通过，60 次检查属于 1 个测试程序。

### 2. 暂停系统，提交 A、B、C

```bash
# 在 missino_node.cpp 中创建的/patrol/cancel_pending服务名称，接口类型 patrol_interfaces::srv::CancelPending
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service type /patrol/cancel_pending
patrol_interfaces/srv/CancelPending

# 暂停系统
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service call patrol/set_paused std_srvs/srv/SetBool '{data: true}'
waiting for service to become available...
requester: making request: std_srvs.srv.SetBool_Request(data=True)

response:
std_srvs.srv.SetBool_Response(success=True, message='Pause updated; status confirms navigation cancellation.')


donk@ubuntu:~/ROS2_patrol_robot$ run_id="cancel-$(date +%s)"
donk@ubuntu:~/ROS2_patrol_robot$ for suffix in A B C; do
  ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
  "{id: ${run_id}-${suffix}, priority: 50, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 30.0}"
done
publisher: beginning loop
publishing #1: patrol_interfaces.msg.Incident(id='cancel-1794709846-A', priority=50, target=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=0, nanosec=0), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=1.0, y=1.0, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))), ttl_sec=600.0, handling_sec=30.0, description='')

publisher: beginning loop
publishing #1: patrol_interfaces.msg.Incident(id='cancel-1794709846-B', priority=50, target=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=0, nanosec=0), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=1.0, y=1.0, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))), ttl_sec=600.0, handling_sec=30.0, description='')

publisher: beginning loop
publishing #1: patrol_interfaces.msg.Incident(id='cancel-1794709846-C', priority=50, target=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=0, nanosec=0), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=1.0, y=1.0, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))), ttl_sec=600.0, handling_sec=30.0, description='')

# 检查topic /patrol/status，这里发现队列长度为3，三条报警都已接收；系统暂停、无活动任务、队列长度为 3。
donk@ubuntu:~/ROS2_patrol_robot$ ros2 topic echo /patrol/status --once
stamp:
  sec: 1794709881
  nanosec: 811069872
state: PAUSED
active_id: ''
active_priority: 0
patrol_index: 3
queue_size: 3
patrol_completed: 3
events_completed: 0
tasks_failed: 0
paused: true
motion_permitted: false
fault: ''
---
```

同时，终端 B：

```text
---
stamp:
  sec: 1794709853
  nanosec: 613983868
monotonic_sec: 2666.631180237
kind: accepted
task_id: cancel-1794709846-A
detail: ''
value: 0.0
---
stamp:
  sec: 1794709854
  nanosec: 910854345
monotonic_sec: 2667.92804672
kind: accepted
task_id: cancel-1794709846-B
detail: ''
value: 0.0
---
stamp:
  sec: 1794709856
  nanosec: 512220937
monotonic_sec: 2669.529416622
kind: accepted
task_id: cancel-1794709846-C
detail: ''
value: 0.0
---
```

### 3. 撤销排队中的 A B C

操作终端：

```text
# --------------撤销 B--------------
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service call /patrol/cancel_pending patrol_interfaces/srv/CancelPending "{id: ${run_id}-B}"
waiting for service to become available...
requester: making request: patrol_interfaces.srv.CancelPending_Request(id='cancel-1794709846-B')

response:
patrol_interfaces.srv.CancelPending_Response(success=True, message='Pending incident cancelled.')

# 队列长度只有2了，撤销成功队列中的B
donk@ubuntu:~/ROS2_patrol_robot$ ros2 topic echo /patrol/status --once
stamp:
  sec: 1794709969
  nanosec: 510505321
state: PAUSED
active_id: ''
active_priority: 0
patrol_index: 3
queue_size: 2
patrol_completed: 3
events_completed: 0
tasks_failed: 0
paused: true
motion_permitted: false
fault: ''
---

# --------------撤销 A--------------
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service call /patrol/cancel_pending patrol_interfaces/srv/CancelPending "{id: ${run_id}-A}"
waiting for service to become available...
requester: making request: patrol_interfaces.srv.CancelPending_Request(id='cancel-1794713401-A')

response:
patrol_interfaces.srv.CancelPending_Response(success=True, message='Pending incident cancelled.')

donk@ubuntu:~/ROS2_patrol_robot$ ros2 topic echo /patrol/status --once
stamp:
  sec: 1794713769
  nanosec: 795119863
state: PAUSED
active_id: ''
active_priority: 0
patrol_index: 2
queue_size: 1
patrol_completed: 2
events_completed: 0
tasks_failed: 0
paused: true
motion_permitted: false
fault: ''
---

# --------------撤销 C--------------
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service call /patrol/cancel_pending patrol_interfaces/srv/CancelPending "{id: ${run_id}-C}"
waiting for service to become available...
requester: making request: patrol_interfaces.srv.CancelPending_Request(id='cancel-1794713401-C')

response:
patrol_interfaces.srv.CancelPending_Response(success=True, message='Pending incident cancelled.')

donk@ubuntu:~/ROS2_patrol_robot$ ros2 topic echo /patrol/status --once
stamp:
  sec: 1794713778
  nanosec: 296158213
state: PAUSED
active_id: ''
active_priority: 0
patrol_index: 2
queue_size: 0
patrol_completed: 2
events_completed: 0
tasks_failed: 0
paused: true
motion_permitted: false
fault: ''
---
```

## 任务 8：为 Nav2 目标增加反馈观察

**目标：** 导航过程中，打印当前任务、此次导航的编号和剩余距离，并控制日志频率。

**输入：** Nav2 返回的导航反馈，以及本次派发时保存的任务 ID 和 token。

**处理：** 在 `start()` 注册反馈回调，检查 token、导航和取消状态，读取 `distance_remaining` 并限频打印。

**输出：** 主系统终端显示 `feedback id=... token=... remaining=... m`。

**怎么验证成功：** 

输入一次low级别的报警事件，看终端是否显示

```BASH
# 终端B
# ros2 topic pub --once 话题名称 消息类型 "消息内容"
# Incident对应/src/patrol_interfaces/msg/Incident.msg
run_id="feedback-$(date +%s)"
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident "{id: ${run_id}-low, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"

#终端A
[bt_navigator-9] [WARN] [1794809128.125415523] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[controller_server-5] [WARN] [1794809128.188720248] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[mission_manager-12] [INFO] [1794809128.595724769] [mission_manager]: received=2 id=feedback-1794808893-low priority=20
[mission_manager-12] [INFO] [1794809128.607637434] [mission_manager]: accepted feedback-1794808893-low 
[mission_manager-12] [INFO] [1794809128.607824694] [mission_manager]: cancel_requested patrol/3 preempt
[mission_manager-12] [INFO] [1794809128.707701904] [mission_manager]: cancelled patrol/3 preempt
[mission_manager-12] [INFO] [1794809128.707738613] [mission_manager]: TASK8_READY id=feedback-1794808893-low
[mission_manager-12] [INFO] [1794809128.709850732] [mission_manager]: dispatched feedback-1794808893-low 
[mission_manager-12] [INFO] [1794809128.736634128] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=4.75 m
[mission_manager-12] [INFO] [1794809129.762647491] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=1.30 m
[mission_manager-12] [INFO] [1794809130.763810454] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=1.33 m
[mission_manager-12] [INFO] [1794809131.812574729] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=1.15 m
[mission_manager-12] [INFO] [1794809132.812635214] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=0.90 m
[mission_manager-12] [INFO] [1794809133.862511173] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=0.64 m
[mission_manager-12] [INFO] [1794809134.912633429] [mission_manager]: feedback id=feedback-1794808893-low token=17 remaining=0.37 m
[mission_manager-12] [INFO] [1794809135.902798145] [mission_manager]: arrived feedback-1794808893-low 
[mission_manager-12] [INFO] [1794809138.902869076] [mission_manager]: completed feedback-1794808893-low 
[mission_manager-12] [INFO] [1794809138.952110072] [mission_manager]: TASK8_READY id=patrol/3
```

主系统出现报警、机器人仍在导航时暂停

```bash
#终端B
run_id="feedback-$(date +%s)"
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident "{id: ${run_id}-low, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"

ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'

ros2 topic echo /patrol/status --once
---
stamp:
  sec: 1794809372
  nanosec: 960383743
state: PAUSED
active_id: ''
active_priority: 0
patrol_index: 0
queue_size: 1
patrol_completed: 20
events_completed: 1
tasks_failed: 0
paused: true
motion_permitted: false
fault: ''
---

#终端A
[controller_server-5] [WARN] [1794809340.515769951] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[bt_navigator-9] [WARN] [1794809340.568559265] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[mission_manager-12] [INFO] [1794809340.901318252] [mission_manager]: arrived patrol/0 
[mission_manager-12] [INFO] [1794809341.102783333] [mission_manager]: received=5 id=feedback-1794809315-low priority=20
[mission_manager-12] [INFO] [1794809341.158525083] [mission_manager]: accepted feedback-1794809315-low 
[mission_manager-12] [INFO] [1794809341.202894199] [mission_manager]: TASK8_READY id=feedback-1794809315-low
[mission_manager-12] [INFO] [1794809341.211661422] [mission_manager]: dispatched feedback-1794809315-low 
[mission_manager-12] [INFO] [1794809341.242539051] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=0.22 m
[mission_manager-12] [INFO] [1794809342.265494267] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=8.15 m
[mission_manager-12] [INFO] [1794809343.315655765] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=7.87 m
[mission_manager-12] [INFO] [1794809344.365559792] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=7.60 m
[mission_manager-12] [INFO] [1794809345.415531659] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=7.32 m
[mission_manager-12] [INFO] [1794809346.415631758] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=7.07 m
[mission_manager-12] [INFO] [1794809347.415637218] [mission_manager]: feedback id=feedback-1794809315-low token=25 remaining=6.80 m
[bt_navigator-9] [WARN] [1794809348.278439555] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[bt_navigator-9] [WARN] [1794809348.278490746] [bt_navigator_navigate_to_pose_rclcpp_node]: Timed out while waiting for action server to acknowledge goal request for follow_path
[controller_server-5] [WARN] [1794809348.299220608] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[controller_server-5] [WARN] [1794809348.364248643] [controller_server]: [follow_path] [ActionServer] Aborting handle.
[bt_navigator-9] [WARN] [1794809348.430737065] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[mission_manager-12] [INFO] [1794809348.449043339] [mission_manager]: paused feedback-1794809315-low 
[mission_manager-12] [INFO] [1794809348.449110366] [mission_manager]: cancel_requested feedback-1794809315-low pause
[bt_navigator-9] [ERROR] [1794809348.586588147] [bt_navigator_navigate_to_pose_rclcpp_node]: Failed to get result for follow_path in node halt!
[mission_manager-12] [INFO] [1794809348.604333325] [mission_manager]: cancelled feedback-1794809315-low pause
[controller_server-5] [WARN] [1794809348.619251957] [controller_server]: Control loop missed its desired rate of 10.0000Hz
```

接着取消暂停

```BASH
#终端B
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'

#终端A
[mission_manager-12] [INFO] [1794809398.353209892] [mission_manager]: resumed  
[mission_manager-12] [INFO] [1794809398.353250821] [mission_manager]: TASK8_READY id=feedback-1794809315-low
[mission_manager-12] [INFO] [1794809398.353310520] [mission_manager]: dispatched feedback-1794809315-low 
[mission_manager-12] [INFO] [1794809398.415745035] [mission_manager]: feedback id=feedback-1794809315-low token=26 remaining=6.52 m
```

验证高优先级抢占

```BASH
#终端B
run_id="feedback-$(date +%s)"
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident "{id: ${run_id}-low, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"
#随后快速再输入
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident "{id: ${run_id}-urgent, priority: 100, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"

#终端A
[controller_server-5] [WARN] [1794809486.110027318] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[mission_manager-12] [INFO] [1794809486.553344151] [mission_manager]: received=7 id=feedback-1794809481-low priority=20
[mission_manager-12] [INFO] [1794809486.594531859] [mission_manager]: accepted feedback-1794809481-low 
[mission_manager-12] [INFO] [1794809486.594994533] [mission_manager]: cancel_requested patrol/1 preempt
[mission_manager-12] [INFO] [1794809486.695058348] [mission_manager]: cancelled patrol/1 preempt
[mission_manager-12] [INFO] [1794809486.695096663] [mission_manager]: TASK8_READY id=feedback-1794809481-low
[mission_manager-12] [INFO] [1794809486.696012642] [mission_manager]: dispatched feedback-1794809481-low 
[mission_manager-12] [INFO] [1794809486.715520314] [mission_manager]: feedback id=feedback-1794809481-low token=29 remaining=0.92 m
[mission_manager-12] [INFO] [1794809487.752104629] [mission_manager]: feedback id=feedback-1794809481-low token=29 remaining=5.97 m
[mission_manager-12] [INFO] [1794809488.752206356] [mission_manager]: feedback id=feedback-1794809481-low token=29 remaining=5.70 m
[controller_server-5] [WARN] [1794809492.704214494] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[bt_navigator-9] [WARN] [1794809492.711331613] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[mission_manager-12] [INFO] [1794809492.806146872] [mission_manager]: feedback id=feedback-1794809481-low token=29 remaining=4.72 m
[controller_server-5] [WARN] [1794809492.880981942] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[mission_manager-12] [INFO] [1794809493.288828097] [mission_manager]: received=8 id=feedback-1794809481-urgent priority=100
[mission_manager-12] [INFO] [1794809493.293412353] [mission_manager]: accepted feedback-1794809481-urgent 
[mission_manager-12] [INFO] [1794809493.293542348] [mission_manager]: cancel_requested feedback-1794809481-low preempt
[mission_manager-12] [INFO] [1794809493.447374988] [mission_manager]: cancelled feedback-1794809481-low preempt
[mission_manager-12] [INFO] [1794809493.447411768] [mission_manager]: TASK8_READY id=feedback-1794809481-urgent
[mission_manager-12] [INFO] [1794809493.447507609] [mission_manager]: dispatched feedback-1794809481-urgent 
[mission_manager-12] [INFO] [1794809493.454731726] [mission_manager]: feedback id=feedback-1794809481-urgent token=30 remaining=4.55 m
[mission_manager-12] [INFO] [1794809494.501853654] [mission_manager]: feedback id=feedback-1794809481-urgent token=30 remaining=6.97 m
[mission_manager-12] [INFO] [1794809495.503094822] [mission_manager]: feedback id=feedback-1794809481-urgent token=30 remaining=6.77 m

[mission_manager-12] [INFO] [1794809524.992679396] [mission_manager]: arrived feedback-1794809481-urgent 
[mission_manager-12] [INFO] [1794809527.992562255] [mission_manager]: completed feedback-1794809481-urgent 
[mission_manager-12] [INFO] [1794809528.042519291] [mission_manager]: TASK8_READY id=feedback-1794809481-low
[mission_manager-12] [INFO] [1794809528.042662616] [mission_manager]: dispatched feedback-1794809481-low 
[mission_manager-12] [INFO] [1794809528.046558213] [mission_manager]: feedback id=feedback-1794809481-low token=31 remaining=0.21 m
[mission_manager-12] [INFO] [1794809529.094386638] [mission_manager]: feedback id=feedback-1794809481-low token=31 remaining=5.65 m
[mission_manager-12] [INFO] [1794809530.143828001] [mission_manager]: feedback id=feedback-1794809481-low token=31 remaining=5.37 m
```

### 本次验证结论（2026-11-16 核对）

- 报警导航：`feedback-1794808893-low` 的 token=17 连续输出距离，随后到达、约 3 秒后完成，符合预期。
- 暂停恢复：`feedback-1794809315-low` 暂停前 token=25，取消后重新排队（queue_size=1），恢复后同一 ID 使用 token=26；记录片段中暂停后不再输出 token=25。
- 高优先级抢占：低优先级 token=29 → 取消旧导航 → 紧急任务 token=30 → 紧急任务到达并完成 → 恢复原低优先级任务 token=31。该片段中的任务 ID 与编号切换符合预期。
- 限频：按同一 ID/token 分组，相邻反馈日志间隔约 1.000～1.051 秒，符合清理前每秒最多输出一次的设置。

### 日志清理后的查看方式

删除 `TASK8_READY`、`TASK8_FEEDBACK_RECEIVED` 临时标记。报警反馈仍每秒一次，普通巡逻改为每五秒一次；重复接收计数和巡逻到达/完成日志改为 DEBUG。任务话题和 CSV 继续保留完整事件。

默认启动时 Nav2 只显示 ERROR 及以上日志；开启 WARN 可检查本轮出现过的控制频率、行为树超时等警告。减少显示内容并不表示这些问题已经修复。

```bash
# 需要诊断时，先退出旧系统，再用此命令重启
bash scripts/run.sh rviz:=false nav_log_level:=warn mission_log_level:=debug
```

### 首帧距离修复（代码已修改，待 Ubuntu 复测）

- 不采用“跳过第一帧”或固定延时。新增全局路径订阅；每次派发、暂停恢复重派、抢占重派都清空距离缓存。
- 路径必须在本次派发之后生成，坐标系匹配，终点距离当前目标不超过 0.5 m（与当前 Navfn 规划终点容差对应）；乱序和旧路径不替换已接受路径。
- 使用这条路径与 Action 反馈中的当前位置，计算到路径投影点的连接距离及后续路径长度。位置时间戳必须不早于该路径生成时间。
- 尚未拿到当前路径或对应位置时，只输出一次 `remaining=WAITING_FOR_CURRENT_PLAN`；有效数字首次出现不必等待巡逻的 5 秒限频周期。
- 数字日志标注 `source=current_plan`，属于本节点基于当前规划的路径距离估计；原始 Nav2 数值仅在 DEBUG 的 `feedback_raw ... nav_remaining=...` 中保留。`/plan` 没有 Action UUID，当前项目用时间、坐标系和终点关联目标。
- 到达、完成、取消及任务调度继续使用原有 Action 结果；显示的距离不参与这些决策。

## 任务 9：完成调试与回归交付

**目标：**看清程序怎么运行，并让验证过程能够重复，这里选择分步骤验证的方式进行实验。

**第一步：**用GDB观察一次撤销

调试对象：`mission.hpp`的`cancel_pending (line 79)`，其业务是：找到排队任务，撤销它，记录撤销，找不到则返回失败。

```bash
# 构建Debug版本
colcon build --symlink-install --packages-up-to patrol_manager --cmake-args -DBUILD_TESTING=ON -DCMAKE_BUILD_TYPE=Debug
source install/setup.bash

# 调试核心测试程序
gdb build/patrol_manager/test_mission
break patrol::Mission::cancel_pending
```

第一次调用

```bash
# 对应test_mission.cpp中的：m=make();
# 第一次停在断点m.cancel_pending("missing")
run
print id
	$1 = "missing"
print queue
	$2 = std::vector of length 0, capacity 0
```

第二次调用

```bash
# 对应test_mission.cpp中的：m=mak();m.submit(event("a",20),0);m.submit(event("b",80),0);m.submit(event("c",20),0);
# 第二次停在断点m.cancel_pending("missing")
# 让当前这一次函数调用执行完，返回调用它的位置，并显示返回值
# 继续执行整个程序，直到再次遇到断点、程序结束或其他停止事件
finish
Run till exit from #0  patrol::Mission::cancel_pending (this=0x7fffffffd7a0, id="missing")
    at /home/donk/ROS2_patrol_robot/src/patrol_manager/include/patrol_manager/mission.hpp:79
0x00005555555588f2 in main () at /home/donk/ROS2_patrol_robot/src/patrol_manager/test/test_mission.cpp:70
70	      check(!m.cancel_pending("missing"),"empty queue cancellation returns false");
Value returned is $5 = false

continue
print id
$6 = "missing"
print queue
    $7 = std::vector of length 3, capacity 4 = {{id = "a", pose = {x = 2, y = 2, yaw = 0}, priority = 20, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 1}, {id = "b", pose = {x = 2, y = 2, yaw = 0}, priority = 80, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 2}, {id = "c", pose = {x = 2, y = 2, yaw = 0}, priority = 20, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 3}}
```

第三次调用

```bash
# 第三次停在断点cancel_pending("b")，进入删除B的流程
finish
Run till exit from #0  patrol::Mission::cancel_pending (this=0x7fffffffd7a0, id="missing")
    at /home/donk/ROS2_patrol_robot/src/patrol_manager/include/patrol_manager/mission.hpp:79
0x0000555555558be0 in main () at /home/donk/ROS2_patrol_robot/src/patrol_manager/test/test_mission.cpp:74
74	      check(!m.cancel_pending("missing"),"unknown ID returns false");
Value returned is $8 = false

conitune
print id
    $9 = "b"
print queue
    $10 = std::vector of length 3, capacity 4 = {{id = "a", pose = {x = 2, y = 2, yaw = 0}, priority = 20, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 1}, {id = "b", pose = {x = 2, y = 2, yaw = 0}, priority = 80, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 2}, {id = "c", pose = {x = 2, y = 2, yaw = 0}, priority = 20, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 3}}

# 逐条next，走过queue.erase(it)后查看
print queue
    $12 = std::vector of length 2, capacity 4 = {{id = "a", pose = {x = 2, y = 2, yaw = 0}, priority = 20, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 1}, {id = "c", pose = {x = 2, y = 2, yaw = 0}, priority = 20, event = true, received = 0, expires = 100, 
        handling = 1, retries = 0, order = 3}}

# finish
finish
    Run till exit from #0  patrol::Mission::cancel_pending (this=0x7fffffffd7a0, id="b")
        at /home/donk/ROS2_patrol_robot/src/patrol_manager/include/patrol_manager/mission.hpp:84
    0x0000555555558d5d in main () at /home/donk/ROS2_patrol_robot/src/patrol_manager/test/test_mission.cpp:78
    78	      check(m.cancel_pending("b"),"cancel middle pending event");
    Value returned is $13 = true
```

**第二步：**让观察节点随系统一起启动

`system.launch.py (line 94)`，在`setup()`中，`nodes += [...]`后加入如下代码，让Launch负责按配置启动和管理这些进程

```python
nodes.append(node('patrol_manager', 'patrol_node', parameters=[{'use_sim_time': sim_time}]))
# patrol_manager：程序所在的包。
# patrol_node：CMake 构建并安装的可执行文件。
# parameters：启动时传给节点的参数。
```

`system.launch.py (line 35)`，将`patrol_node`普通节点设置成INFO等级日志

```python
elif node_name in ('control_panel', 'patrol_node'):
```

**第三步：**把手工撤销过程写成自动验收

`tools\ros_acceptance.py`

`Acceptance()`类增加`cancel_pending(self, ident)`，等服务 → 填请求 → 发请求 → 等响应 → 返回结果
`incident()`增加可选TTL，避免较长测试中等待自然任务自然过期
加入验收方法`check_pending_cancellation(self, suffix)`
并在`run()`中调用验收方法`self.check_pending_cancellation(suffix)`，并且在返回结果的`cases`列表中补上如下：

```python
'pending cancellation',
'repeated and unknown cancellation rejected',
'active task protected',
'remaining FIFO preserved',
'cancelled incident not dispatched',
```

`main()`的`try`与`finally`之间增加如下，失败原因也会写入原有的`ros_acceptance.json`，终端仍保留异常调用栈

```python
except Exception as error:
    result = {'result': 'FAIL', 'error': str(error)}
    raise
```









