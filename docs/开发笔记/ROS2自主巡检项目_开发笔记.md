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



我已经按照要求，配置好了autodl中的云服务器，接下来交给你配置好，然后继续跑上次的实验，我希望你能让autodl中的云服务器自己跑程序，因为这次autodl中的云服务器会保留15天的数据，这样就不会受到我自己电脑断网的影响，但数据下载到本地像之前那样也要同步进行（大概率不会断网，所以ssh连接大概率稳固）。
