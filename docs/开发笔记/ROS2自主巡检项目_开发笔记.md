# ROS2 自主巡检项目：开发笔记

一个任务只记四件事：输入、处理、输出、怎么验证成功。具体实现直接回源码看。

以下命令在 Ubuntu 执行，工程路径按实际位置替换。每个新终端先加载环境；修改源码后先退出旧程序，再编译并重启。

```bash
cd ~/ROS2_patrol_robot
source /opt/ros/humble/setup.bash
source install/setup.bash

# 刚刚clone项目时，先完整编译一遍
colcon build --symlink-install

# 修改源码后执行
colcon build --packages-select patrol_manager --symlink-install
source install/setup.bash
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

**目标：**导航过程中，打印当前任务、此次导航的编号和剩余距离，并控制日志频率**

**输入：** 

**处理：** 

**输出：** 

**怎么验证成功：** 

```
#终端C
donk@ubuntu:~/ROS2_patrol_robot$ run_id="feedback-$(date +%s)"
donk@ubuntu:~/ROS2_patrol_robot$ ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
> "{id: ${run_id}-low, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"
Waiting for at least 1 matching subscription(s)...
publisher: beginning loop
publishing #1: patrol_interfaces.msg.Incident(id='feedback-1794807277-low', priority=20, target=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=0, nanosec=0), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=7.0, y=7.0, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))), ttl_sec=600.0, handling_sec=3.0, description='')

#终端B
---
stamp:
  sec: 1794807311
  nanosec: 250859036
monotonic_sec: 4233.852046921
kind: dispatched
task_id: feedback-1794807277-low
detail: ''
value: 0.13640745900011098
---
stamp:
  sec: 1794807338
  nanosec: 196814140
monotonic_sec: 4260.798235827
kind: arrived
task_id: feedback-1794807277-low
detail: ''
value: 27.042978071000107
---
stamp:
  sec: 1794807341
  nanosec: 196935061
monotonic_sec: 4263.798367759
kind: completed
task_id: feedback-1794807277-low
detail: ''
value: 0.0
---

#终端A
[mission_manager-12] [INFO] [1794807311.114033024] [mission_manager]: received=1 id=feedback-1794807277-low priority=20
[mission_manager-12] [INFO] [1794807311.147661058] [mission_manager]: accepted feedback-1794807277-low 
[mission_manager-12] [INFO] [1794807311.147759084] [mission_manager]: cancel_requested patrol/1 preempt
[mission_manager-12] [INFO] [1794807311.250793745] [mission_manager]: cancelled patrol/1 preempt
[mission_manager-12] [INFO] [1794807311.259286228] [mission_manager]: dispatched feedback-1794807277-low 
[mission_manager-12] [INFO] [1794807338.198329852] [mission_manager]: arrived feedback-1794807277-low 
[mission_manager-12] [INFO] [1794807341.198285307] [mission_manager]: completed feedback-1794807277-low 

```

这次暂停在主系统出现报警、机器人仍在导航时

```
#终端C
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service call /patrol/set_paused \
  std_srvs/srv/SetBool '{data: true}'
waiting for service to become available...
requester: making request: std_srvs.srv.SetBool_Request(data=True)

response:
std_srvs.srv.SetBool_Response(success=True, message='Pause updated; status confirms navigation cancellation.')

donk@ubuntu:~/ROS2_patrol_robot$ ros2 topic echo /patrol/status --once
stamp:
  sec: 1794807448
  nanosec: 804466918
state: PAUSED
active_id: ''
active_priority: 0
patrol_index: 0
queue_size: 0
patrol_completed: 8
events_completed: 1
tasks_failed: 0
paused: true
motion_permitted: false
fault: ''
---

#终端B
---
stamp:
  sec: 1794807425
  nanosec: 552702089
monotonic_sec: 4348.15391001
kind: dispatched
task_id: patrol/0
detail: ''
value: 0.0
---
stamp:
  sec: 1794807428
  nanosec: 202735001
monotonic_sec: 4350.804155343
kind: duplicate
task_id: feedback-1794807277-low
detail: ignored
value: 0.0
---
stamp:
  sec: 1794807438
  nanosec: 560223167
monotonic_sec: 4361.161646556
kind: paused
task_id: patrol/0
detail: ''
value: 0.0
---
stamp:
  sec: 1794807438
  nanosec: 605653725
monotonic_sec: 4361.161646556
kind: cancel_requested
task_id: patrol/0
detail: pause
value: 0.0
---
stamp:
  sec: 1794807438
  nanosec: 802465228
monotonic_sec: 4361.403895019
kind: cancelled
task_id: patrol/0
detail: pause
value: 0.0
---

#终端A
[bt_navigator-9] [WARN] [1794807427.509651907] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[bt_navigator-9] [WARN] [1794807427.604996714] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[controller_server-5] [WARN] [1794807427.664340199] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[mission_manager-12] [INFO] [1794807428.182075287] [mission_manager]: received=2 id=feedback-1794807277-low priority=20
[mission_manager-12] [INFO] [1794807428.205539281] [mission_manager]: duplicate feedback-1794807277-low ignored
[bt_navigator-9] [WARN] [1794807438.157841142] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[bt_navigator-9] [WARN] [1794807438.279467815] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[bt_navigator-9] [WARN] [1794807438.279844548] [bt_navigator_navigate_to_pose_rclcpp_node]: Timed out while waiting for action server to acknowledge goal request for compute_path_to_pose
[controller_server-5] [WARN] [1794807438.285246209] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[bt_navigator-9] [WARN] [1794807438.392272406] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[bt_navigator-9] [WARN] [1794807438.392308214] [bt_navigator_navigate_to_pose_rclcpp_node]: Node timed out while executing service call to global_costmap/clear_entirely_global_costmap.
[controller_server-5] [WARN] [1794807438.395160874] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[mission_manager-12] [INFO] [1794807438.562630830] [mission_manager]: paused patrol/0 
[mission_manager-12] [INFO] [1794807438.605724815] [mission_manager]: cancel_requested patrol/0 pause
[bt_navigator-9] [WARN] [1794807438.645807840] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[bt_navigator-9] [ERROR] [1794807438.756476561] [bt_navigator_navigate_to_pose_rclcpp_node]: Failed to get result for compute_path_to_pose in node halt!
[mission_manager-12] [INFO] [1794807438.803799003] [mission_manager]: cancelled patrol/0 pause
[planner_server-7] [WARN] [1794807438.903474589] [planner_server]: Planner loop missed its desired rate of 20.0000 Hz. Current loop rate is 3.7986 Hz

```

接着取消暂停

```
#终端C
donk@ubuntu:~/ROS2_patrol_robot$ ros2 service call /patrol/set_paused \
  std_srvs/srv/SetBool '{data: false}'
waiting for service to become available...
requester: making request: std_srvs.srv.SetBool_Request(data=False)

response:
std_srvs.srv.SetBool_Response(success=True, message='Pause updated; status confirms navigation cancellation.')

#终端B
---
stamp:
  sec: 1794807657
  nanosec: 67109875
monotonic_sec: 4579.668546254
kind: resumed
task_id: ''
detail: ''
value: 0.0
---
stamp:
  sec: 1794807657
  nanosec: 76739215
monotonic_sec: 4579.668546254
kind: dispatched
task_id: patrol/0
detail: ''
value: 0.0
---

#终端A
[mission_manager-12] [INFO] [1794807657.076626211] [mission_manager]: resumed  
[mission_manager-12] [INFO] [1794807657.098800510] [mission_manager]: dispatched patrol/0 
[mission_manager-12] [INFO] [1794807671.512669472] [mission_manager]: arrived patrol/0 
[mission_manager-12] [INFO] [1794807672.512935568] [mission_manager]: completed patrol/0 
[mission_manager-12] [INFO] [1794807672.562981115] [mission_manager]: dispatched patrol/1 
```

验证高优先级抢占

```
#终端C
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-low, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"
#随后快速再输入
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
"{id: ${run_id}-urgent, priority: 100, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 600.0, handling_sec: 3.0}"

#终端B
---
stamp:
  sec: 1794807757
  nanosec: 265652513
monotonic_sec: 4679.867027667
kind: duplicate
task_id: feedback-1794807277-low
detail: ignored
value: 0.0
---
stamp:
  sec: 1794807760
  nanosec: 214669587
monotonic_sec: 4682.8160825
kind: accepted
task_id: feedback-1794807277-urgent
detail: ''
value: 0.0
---
stamp:
  sec: 1794807760
  nanosec: 215919207
monotonic_sec: 4682.8160825
kind: cancel_requested
task_id: patrol/0
detail: preempt
value: 0.0
---


#终端A
[mission_manager-12] [INFO] [1794807757.227828934] [mission_manager]: received=3 id=feedback-1794807277-low priority=20
[mission_manager-12] [INFO] [1794807757.301906731] [mission_manager]: duplicate feedback-1794807277-low ignored
[bt_navigator-9] [WARN] [1794807757.358695415] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[controller_server-5] [WARN] [1794807757.456753435] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[bt_navigator-9] [WARN] [1794807757.466548006] [BehaviorTreeEngine]: Behavior Tree tick rate 20.00 was exceeded!
[controller_server-5] [WARN] [1794807757.478214065] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[controller_server-5] [WARN] [1794807759.706733037] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[controller_server-5] [WARN] [1794807759.787296230] [controller_server]: Control loop missed its desired rate of 10.0000Hz
[mission_manager-12] [INFO] [1794807760.189091152] [mission_manager]: received=4 id=feedback-1794807277-urgent priority=100
[mission_manager-12] [INFO] [1794807760.215740063] [mission_manager]: accepted feedback-1794807277-urgent 
[mission_manager-12] [INFO] [1794807760.216024564] [mission_manager]: cancel_requested patrol/0 preempt
[mission_manager-12] [INFO] [1794807760.318506193] [mission_manager]: cancelled patrol/0 preempt
[mission_manager-12] [INFO] [1794807760.321651459] [mission_manager]: dispatched feedback-1794807277-urgent 
[mission_manager-12] [INFO] [1794807769.064369688] [mission_manager]: arrived feedback-1794807277-urgent 
[mission_manager-12] [INFO] [1794807772.063549856] [mission_manager]: completed feedback-1794807277-urgent 
[mission_manager-12] [INFO] [1794807772.115139588] [mission_manager]: dispatched patrol/0
```





