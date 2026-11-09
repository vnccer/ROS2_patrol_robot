# 一、观察系统正常巡逻（Node、Topic、Service、Action的list）

首先明确三种通信方式：

| 通信方式          | 理解               | 用途举例               | 你的项目中的例子     |
| ----------------- | ------------------ | ---------------------- | -------------------- |
| Topic（发消息）   | 不断广播消息       | 实时位置、摄像头画面   | `/patrol/status`     |
| Service（问问题） | 问一次，答一次     | 暂停巡逻、切换模式     | `/patrol/set_paused` |
| Action（派任务）  | 交代任务，等待完成 | 导航到目标点、执行巡检 | `/navigate_to_pose`  |

```bash
# Terminal1

cd ~/patrol_robot_ws
bash scripts/run.sh
```

```bash
# Terminal2

source /opt/ros/humble/setup.bash
source ~/patrol_robot_ws/install/setup.bash

ros2 node list
ros2 topic list -t # -t 名称 + 消息类型
ros2 action list -t
ros2 service list -t
ros2 topic echo /patrol/status
```

## 1.1 Node list

```bash
donk@ubuntu:~$ ros2 node list
# 任务管理
/mission_manager

# Nav2导航
/bt_navigator
/bt_navigator_navigate_through_poses_rclcpp_node
/bt_navigator_navigate_to_pose_rclcpp_node
/planner_server
/controller_server
/behavior_server
/smoother_server
/global_costmap/global_costmap
/local_costmap/local_costmap

# 机器人仿真
/lightweight_sim

# 运动安全
/velocity_guard
/velocity_smoother

# 地图与坐标
/map_server
/map_to_odom
/robot_state_publisher

# 生命周期与可视化
/lifecycle_manager_patrol
/rviz2

# TF辅助节点
/transform_listener_impl_56c721bd30e0
/transform_listener_impl_5dee3ea39340
/transform_listener_impl_5e00b94a67a0
/transform_listener_impl_61434a015270
/transform_listener_impl_651ceb8c3d80
```

## 1.2 Topic list

Topic是Node之间传递数据的通道，例如`/patrol/status [patrol_interfaces/msg/MissionStatus]`
`/patrol/status`是话题名称，表示任务管理器的运行状态
`patrol_interfaces`是消息所属的ROS2功能包
`msg`表示消息类型
`MissionStatus`是具体消息类型
由于Topic是**发布--订阅通信**，Publisher不断发布消息，`echo`创建一个Subscriber，接收并打印消息，因此可以用`ros2 topic echo /patrol/status`查看此话题正在传输的数据（扒开通道）。

1. 巡逻任务与事件
   | Topic                   | 消息类型      | 作用                           |
   | ----------------------- | ------------- | ------------------------------ |
   | `/patrol/incidents`     | Incident      | 接收报警事件                   |
   | `/patrol/status`        | MissionStatus | 发布巡逻任务状态               |
   | `/patrol/records`       | TaskRecord    | 记录任务接收、抢占、完成等事件 |
   | `/patrol/motion_permit` | Bool          | 发布运动许可                   |

2. 导航与速度
   | Topic          | 作用                             |
   | -------------- | -------------------------------- |
   | `/goal_pose`   | 由 RViz 等工具发布导航目标       |
   | `/plan`        | Nav2 规划的路径                  |
   | `/nav_cmd_vel` | Nav2 输出的速度指令              |
   | `/cmd_vel`     | 经过速度门禁后发送到底盘的速度   |
   | `/odom`        | 机器人里程计，反馈位置和运动信息 |

   Nav2 --`/nav_cmd_vel`-- velocity_guard --`cmd_vel`-- lightweight_sim

3. 传感器与坐标
   | Topic        | 作用             |
   | ------------ | ---------------- |
   | `/scan`      | 激光雷达扫描数据 |
   | `/tf`        | 动态坐标变换     |
   | `/tf_static` | 静态坐标变换     |

```bash
donk@ubuntu:~$ ros2 topic list -t
/behavior_server/transition_event [lifecycle_msgs/msg/TransitionEvent]
/behavior_tree_log [nav2_msgs/msg/BehaviorTreeLog]
/bond [bond/msg/Status]
/bt_navigator/transition_event [lifecycle_msgs/msg/TransitionEvent]
/cmd_vel [geometry_msgs/msg/Twist]
/cmd_vel_teleop [geometry_msgs/msg/Twist]
/controller_server/transition_event [lifecycle_msgs/msg/TransitionEvent]
/cost_cloud [sensor_msgs/msg/PointCloud2]
/diagnostics [diagnostic_msgs/msg/DiagnosticArray]
/evaluation [dwb_msgs/msg/LocalPlanEvaluation]
/global_costmap/costmap [nav_msgs/msg/OccupancyGrid]
/global_costmap/costmap_raw [nav2_msgs/msg/Costmap]
/global_costmap/costmap_updates [map_msgs/msg/OccupancyGridUpdate]
/global_costmap/footprint [geometry_msgs/msg/Polygon]
/global_costmap/global_costmap/transition_event [lifecycle_msgs/msg/TransitionEvent]
/global_costmap/published_footprint [geometry_msgs/msg/PolygonStamped]
/goal_pose [geometry_msgs/msg/PoseStamped]
/joint_states [sensor_msgs/msg/JointState]
/local_costmap/clearing_endpoints [sensor_msgs/msg/PointCloud2]
/local_costmap/costmap [nav_msgs/msg/OccupancyGrid]
/local_costmap/costmap_raw [nav2_msgs/msg/Costmap]
/local_costmap/costmap_updates [map_msgs/msg/OccupancyGridUpdate]
/local_costmap/footprint [geometry_msgs/msg/Polygon]
/local_costmap/local_costmap/transition_event [lifecycle_msgs/msg/TransitionEvent]
/local_costmap/published_footprint [geometry_msgs/msg/PolygonStamped]
/local_costmap/voxel_grid [nav2_msgs/msg/VoxelGrid]
/local_plan [nav_msgs/msg/Path]
/map [nav_msgs/msg/OccupancyGrid]
/map_server/transition_event [lifecycle_msgs/msg/TransitionEvent]
/map_updates [map_msgs/msg/OccupancyGridUpdate]
/marker [visualization_msgs/msg/MarkerArray]
/nav_cmd_vel [geometry_msgs/msg/Twist]
/odom [nav_msgs/msg/Odometry]
/parameter_events [rcl_interfaces/msg/ParameterEvent]
/patrol/incidents [patrol_interfaces/msg/Incident]
/patrol/motion_permit [std_msgs/msg/Bool]
/patrol/records [patrol_interfaces/msg/TaskRecord]
/patrol/status [patrol_interfaces/msg/MissionStatus]
/plan [nav_msgs/msg/Path]
/plan_smoothed [nav_msgs/msg/Path]
/planner_server/transition_event [lifecycle_msgs/msg/TransitionEvent]
/preempt_teleop [std_msgs/msg/Empty]
/raw_cmd_vel [geometry_msgs/msg/Twist]
/received_global_plan [nav_msgs/msg/Path]
/robot_description [std_msgs/msg/String]
/rosout [rcl_interfaces/msg/Log]
/scan [sensor_msgs/msg/LaserScan]
/smoother_server/transition_event [lifecycle_msgs/msg/TransitionEvent]
/speed_limit [nav2_msgs/msg/SpeedLimit]
/tf [tf2_msgs/msg/TFMessage]
/tf_static [tf2_msgs/msg/TFMessage]
/transformed_global_plan [nav_msgs/msg/Path]
/velocity_smoother/transition_event [lifecycle_msgs/msg/TransitionEvent]
```

`ros2 topic echo`看到刷新极快的数据，可以看到两条消息的时间戳`1793682140.143123472`和`1793682140.193965745`，间隔约`0.05s`，约`20Hz`（每秒20条）

```
donk@ubuntu:~$ ros2 topic echo /patrol/status
stamp:
  sec: 1793682140
  nanosec: 143123472
state: PATROLLING       # 状态：正在巡逻
active_id: patrol/1     # 当前正在执行的巡逻任务ID
active_priority: 0
patrol_index: 1         # 当前巡逻点索引
queue_size: 0           # 等待执行的任务数量
patrol_completed: 9     # 已完成23次巡逻任务
events_completed: 0
tasks_failed: 0
paused: false
motion_permitted: true  # 允许机器人运动
fault: ''
---
stamp:
  sec: 1793682140
  nanosec: 193965745
state: PATROLLING
active_id: patrol/1
active_priority: 0
patrol_index: 1
queue_size: 0
patrol_completed: 9
events_completed: 0
tasks_failed: 0
paused: false
motion_permitted: true
fault: ''
---

donk@ubuntu:~/patrol_robot_ws$ ros2 topic hz /patrol/status
average rate: 19.998
	min: 0.025s max: 0.070s std dev: 0.00766s window: 22
```

## 1.3 Action list

最重要的Action：`/navigate_to_pose`

注：与Topic不同，由于Action是一个执行长时间任务的通信机制，没有`ros2 action echo`这个命令

```bash
donk@ubuntu:~$ ros2 action list -t
/assisted_teleop [nav2_msgs/action/AssistedTeleop]
/backup [nav2_msgs/action/BackUp]
/compute_path_through_poses [nav2_msgs/action/ComputePathThroughPoses]
/compute_path_to_pose [nav2_msgs/action/ComputePathToPose]
/drive_on_heading [nav2_msgs/action/DriveOnHeading]
/follow_path [nav2_msgs/action/FollowPath]
/navigate_through_poses [nav2_msgs/action/NavigateThroughPoses]
/navigate_to_pose [nav2_msgs/action/NavigateToPose]
/smooth_path [nav2_msgs/action/SmoothPath]
/spin [nav2_msgs/action/Spin]
/wait [nav2_msgs/action/Wait]
```

查看Action数据结构：`ros2 interface show nav2_msgs/action/NavigateToPose`，包含Goal、Result、Feedback三部分，且由于这个命令会将嵌套消息的字段也展开，所以看起来很长，暂时先不管里面的内容，接着推进下一个Service

```
donk@ubuntu:~/patrol_robot_ws$ ros2 interface show nav2_msgs/action/NavigateToPose 
#goal definition
geometry_msgs/PoseStamped pose
	std_msgs/Header header
		builtin_interfaces/Time stamp
			int32 sec
			uint32 nanosec
		string frame_id
	Pose pose
		Point position
			float64 x
			float64 y
			float64 z
		Quaternion orientation
			float64 x 0
			float64 y 0
			float64 z 0
			float64 w 1
string behavior_tree
---
#result definition
std_msgs/Empty result
---
#feedback definition
geometry_msgs/PoseStamped current_pose
	std_msgs/Header header
		builtin_interfaces/Time stamp
			int32 sec
			uint32 nanosec
		string frame_id
	Pose pose
		Point position
			float64 x
			float64 y
			float64 z
		Quaternion orientation
			float64 x 0
			float64 y 0
			float64 z 0
			float64 w 1
builtin_interfaces/Duration navigation_time
	int32 sec
	uint32 nanosec
builtin_interfaces/Duration estimated_time_remaining
	int32 sec
	uint32 nanosec
int16 number_of_recoveries
float32 distance_remaining
```

查看Action服务器和客户端：`ros2 action info /navigate_to_pose`

```
donk@ubuntu:~/patrol_robot_ws$ ros2 action info /navigate_to_pose
Action: /navigate_to_pose
Action clients: 2
    /bt_navigator
    /mission_manager
Action servers: 1
    /bt_navigator
```

## 1.4 Service list

173个service

```
donk@ubuntu:~/patrol_robot_ws$ ros2 service list -t
/behavior_server/change_state [lifecycle_msgs/srv/ChangeState]
/behavior_server/describe_parameters [rcl_interfaces/srv/DescribeParameters]
/behavior_server/get_available_states [lifecycle_msgs/srv/GetAvailableStates]
/behavior_server/get_available_transitions [lifecycle_msgs/srv/GetAvailableTransitions]
/behavior_server/get_parameter_types [rcl_interfaces/srv/GetParameterTypes]
...
```

| 重要Service              | 类型    | 用途                   |
| ------------------------ | ------- | ---------------------- |
| `/patrol/set_paused`     | SetBool | 人工暂停or恢复任务     |
| `/patrol/emergency_stop` | Trigger | 触发紧急停止并锁存故障 |
| `/patrol/recover`        | Trigger | 健康条件满足后解除故障 |
| `/patrol/sim/drop_odom`  | SetBool | 模拟里程计数据丢失     |
| `/patrol/sim/drop_scan`  | SetBool | 模拟激光雷达数据丢失   |
| `/patrol/sim/drop_scan`  | SetBool | 模拟机器人运动受阻     |

```
# 暂停
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: true}'

# 恢复
ros2 service call /patrol/set_paused std_srvs/srv/SetBool '{data: false}'
```

# 二、`mission_manager`如何通过C++实现Topic订阅、Service服务端和Action客户端

## 2.0 mission_manager源码关系

- `mission_node.cpp`（ROS2 通信层）：负责接收消息、调用 Nav2、发布状态。
- `mission.hpp`（业务逻辑层）：负责巡逻任务、优先级、抢占、故障和恢复。

## 2.1 Topic

Topic负责接收消息；收到消息后，回调将其转换成Task，并调用`submit()`交给业务层

`/patrol_robot_ws/src/patrol_manager/src/mission_node.cpp`中的`create_subscription`

```c++
incidents_=create_subscription<patrol_interfaces::msg::Incident>("patrol/incidents",50,
      [this](patrol_interfaces::msg::Incident::ConstSharedPtr m){
        auto &q=m->target.pose.orientation;
        double norm=q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w;
        if(m->target.header.frame_id!=frame_ || !std::isfinite(norm) || std::abs(norm-1)>0.05) {
          mission_->record("rejected","frame must be map and quaternion normalized",0,m->id); return;
        }
        patrol::Task t; t.id=m->id; t.priority=m->priority;
        t.pose={m->target.pose.position.x,m->target.pose.position.y,
          std::atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))};
        t.expires=m->ttl_sec; t.handling=m->handling_sec;
        mission_->submit(t,wall_now());
      });
```

1. 创建订阅者
   ```
   create_subscription<patrol_interfaces::msg::Incident>(
   	"patrol/incidents", 50, ...
   );
   
   # 订阅的消息类型为Incident
   # 订阅的话题名称为patrol/incidents
   # QoS的历史深度为50
   ```

2. 检查、转换报警事件
   收到消息后，代码先检查坐标系和四元数是否符合要求，然后把 ROS2 的 `Incident` 消息转换成业务层使用的 `patrol::Task`。
   例如发送：

   ```
   id: alarm-001
   priority: 80
   target: (6.5, 6.5)
   ttl_sec: 180
   handling_sec: 3
   
   # C++会提取这些字段，构造一个 Task 对象
   ```

3. 交给任务调度器
   ```
   mission_->submit(t,wall_now());
   
   # mission_指向patrol::Mission对象
   # submit()提交新的任务
   # t是刚刚转换好的事件任务
   # wall_now()用于任务超时计算的单调时钟时间
   ```

## 2.2 Service

三个service：`patrol/set_pause`、`patrol/emergency_stop`、`patrol/recover`，先研究第一个

看源码：`/patrol_robot_ws/src/patrol_manager/src/mission_node.cpp`中的`create_service`

1. `create_service()`创建服务器

   ```C++
   pause_=create_service<std_srvs::srv::SetBool>("patrol/set_paused", ...);
   
   /*
   create_service()	ROS2 提供的创建 Service 服务端的函数
   <std_srvs::srv::SetBool>	指定服务类型，接收布尔值 true/false
   "patrol/set_paused"	服务名称，在当前根命名空间下为 /patrol/set_paused
   #pause_	保存 Service 对象，保证服务端持续存在
   */
   ```

2. `[this](...req,...res)`接收请求的回调函数

   ```C++
   [this](std_srvs::srv::SetBool::Request::SharedPtr req,
          std_srvs::srv::SetBool::Response::SharedPtr res)
   
   /*
   [this]：允许回调访问当前 MissionNode 对象的成员。
   SharedPtr：共享智能指针，用于访问请求和响应对象。
   req / res：分别表示请求（Request）和响应（Response）。
   */
   ```

3. `mission_->pause()`真正修改业务状态

   ```C++
   mission_->pause(req->data,wall_now()); publish_permit();
   
   /*
   req->data：读取外部传入的 true 或 false。
   wall_now()：获取当前单调时钟时间。
   mission_->pause()：调用 mission.hpp 中的业务函数。
   publish_permit()：更新并发布运动许可状态。
   */
   ```

   同时查看`mission.hpp`中的代码

   ```C++
   void pause(bool value, double now) {
       if (value==paused) return;
       paused=value;
       record(value ? "paused" : "resumed");
       if (value) suspend(now,"pause");
   }
   
   /*
   paused=value 这行代码将外部请求转化为内部业务状态，
   当value为true，会通过suspend()中断当前任务，
   但注：暂停请求被接收，不代表 Nav2 已经完成导航取消
   */
   ```

4. `res->success`给客户端返回结果

   ```C++
   res->success=true; res->message="Pause updated; status confirms navigation cancellation.";
   
   /*
   向service客户端返回信息，暂停处理，但导航取消是否完成需要继续观察
   */
   ```

完整源码：

```C++
pause_=create_service<std_srvs::srv::SetBool>("patrol/set_paused",  //  客户端发送请求
  [this](std_srvs::srv::SetBool::Request::SharedPtr req,std_srvs::srv::SetBool::Response::SharedPtr res){  //  服务端回调
    mission_->pause(req->data,wall_now()); publish_permit();  //  修改业务状态
    res->success=true; res->message="Pause updated; status confirms navigation cancellation.";  //  返回响应
  });
```

实操：

```bash
	# 找/patrol/set_paused 这个service，并且看[]中的服务类型
donk@ubuntu:~/patrol_robot_ws$ ros2 service list -t | grep set_paused
/patrol/set_paused [std_srvs/srv/SetBool]

	# 调用/patrol/set_paused暂停
donk@ubuntu:~/patrol_robot_ws$ ros2 service call /patrol/set_paused std_srvs/srv/SetBool "{data: true}"
waiting for service to become available...
requester: making request: std_srvs.srv.SetBool_Request(data=True)

response:
std_srvs.srv.SetBool_Response(success=True, message='Pause updated; status confirms navigation cancellation.')

	# 查看/patrol/status节点状态，paused: true
donk@ubuntu:~/patrol_robot_ws$ ros2 topic echo /patrol/status --once
...
paused: true
...

	# 调用/patrol/set_paused取消暂停
donk@ubuntu:~/patrol_robot_ws$ ros2 service call /patrol/set_paused std_srvs/srv/SetBool "{data: false}"
waiting for service to become available...
requester: making request: std_srvs.srv.SetBool_Request(data=False)

response:
std_srvs.srv.SetBool_Response(success=True, message='Pause updated; status confirms navigation cancellation.')

	# 查看/patrol/status节点状态，paused: false
donk@ubuntu:~/patrol_robot_ws$ ros2 topic echo /patrol/status --once
...
paused: false
...
```

## 2.3 Action

**源码：**`/patrol_robot_ws/src/patrol_manager/src/mission_node.cpp`中的`create_client`、`async_send_goal`、`result_callback`

1. `create_client()`创建Action客户端

   ```C++
   // 24行，让Nav代表ROS2的 nav2_msgs::action::NavigateToPose
   using Nav = nav2_msgs::action::NavigateToPose;
   
   // 68行，创建Action客户端
   nav_=rclcpp_action::create_client<Nav>(this,"navigate_to_pose");
   /*
   rclcpp_action 是ROS2 C++的Action功能库
   create_client<>() 创建NavigateToPose类型的Action客户端
   this 指当前MissionNode对象
   "navigate_to_pose" 指要连接的Action名称
   nav_ 保存创建的客户端对象
   */
   
   // 69行，要区分，这里创建的是Service服务端，而非Action客户端
   lifecycle_=create_client<lifecycle_msgs::srv::GetState>("bt_navigator/get_state");
   ```

2. `async_send_goal()`异步发送导航目标

   ```c++
   void start(const patrol::Effect &e) {
     Nav::Goal goal;
     goal.pose.header.frame_id=frame_; goal.pose.header.stamp=now();
     goal.pose.pose.position.x=e.task.pose.x; goal.pose.pose.position.y=e.task.pose.y;
     goal.pose.pose.orientation.z=std::sin(e.task.pose.yaw/2);
     goal.pose.pose.orientation.w=std::cos(e.task.pose.yaw/2);
     const auto token=e.token;
     auto options=rclcpp_action::Client<Nav>::SendGoalOptions();
     options.goal_response_callback=[this,token](Handle::SharedPtr h){
       if(token!=mission_->token) return;
       handle_=h;
       if(!h) mission_->result(token,false,wall_now());
       else if(mission_->cancelling) cancel();
     };
     options.result_callback=[this,token](const Handle::WrappedResult &r){
       if(token!=mission_->token) return;
       handle_.reset(); mission_->result(token,r.code==rclcpp_action::ResultCode::SUCCEEDED,wall_now());
     };
     try {nav_->async_send_goal(goal,options);}
     catch(const std::exception &err) {
       mission_->result(token,false,wall_now()); mission_->trip(err.what(),wall_now());
     }
   }
   
   // start()函数中先创建导航目标
   // 其中goal.pose.pose.position.x=e.task.pose.x; goal.pose.pose.position.y=e.task.pose.y;，把任务中的目标坐标写进Nav2导航请求
   
   // nav_->async_send_goal(goal,options);中的
   // goal是去哪里
   // optins是收到目标响应or导航结果时，应该执行哪些回调函数
   // async是asynchronous（异步），意味着发送导航请求后，程序不必停在这一行等待机器人到达目标
   ```

3. `result_callback`Nav2返回最终结果时，ROS2自动执行的回调函数

   ```c++
   // 设置了两个回调
   
   // 1.目标响应回调
   options.goal_response_callback=[this,token](Handle::SharedPtr h){
     if(token!=mission_->token) return;
     handle_=h;
     if(!h) mission_->result(token,false,wall_now());
     else if(mission_->cancelling) cancel();
   };
   /*
   确认Nav2是否接受了导航目标
   [this,token]是Lambda捕获列表，表示回调可以使用当前对象this和发送目标时保存的token
   */
   
   // 2.最终结果回调
   options.result_callback=[this,token](const Handle::WrappedResult &r){
     if(token!=mission_->token) return;
     handle_.reset();
     mission_->result(
       token,
       r.code==rclcpp_action::ResultCode::SUCCEEDED,
       wall_now()
     );
   };
   /*
   判断导航是否成功，成功向mission_->result()传入true，没有成功传入false
   */
   ```

实操：

```BASH
	#1.查看Action客户端与服务端。证明c++程序创建了Action客户端，且Nav2提供了对应服务端
donk@ubuntu:~$ ros2 action info /navigate_to_pose
Action: /navigate_to_pose
Action clients: 2
    /bt_navigator
    /mission_manager
Action servers: 1
    /bt_navigator

	#2.发送一个报警，观察Action被触发
TerminalA
donk@ubuntu:~$ ros2 topic echo /patrol/records

TerminalB
donk@ubuntu:~$ ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident '{id: action-test-001, priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}'
publisher: beginning loop
publishing #1: patrol_interfaces.msg.Incident(id='action-test-001', priority=80, target=geometry_msgs.msg.PoseStamped(header=std_msgs.msg.Header(stamp=builtin_interfaces.msg.Time(sec=0, nanosec=0), frame_id='map'), pose=geometry_msgs.msg.Pose(position=geometry_msgs.msg.Point(x=1.0, y=1.0, z=0.0), orientation=geometry_msgs.msg.Quaternion(x=0.0, y=0.0, z=0.0, w=1.0))), ttl_sec=180.0, handling_sec=3.0, description='')
# Topic发送成功
# x=1.0, y=1.0为报警目标位置
# frame_id='map'使用地图坐标系
# ttl_sec=180.0 任务有效期180s
# handling_sec=3.0 到达后预设处理时间3s

	#3.观察Action被触发
TerminalA（与action-test-001相关）
---
stamp:
  sec: 1793877608
  nanosec: 902595636
monotonic_sec: 17789.575092781
kind: accepted
task_id: action-test-001
detail: ''
value: 0.0
---
stamp:
  sec: 1793877608
  nanosec: 955875940
monotonic_sec: 17789.625122596
kind: dispatched
task_id: action-test-001
detail: ''
value: 0.06995893299972522
---
stamp:
  sec: 1793877631
  nanosec: 802101425
monotonic_sec: 17812.474622531
kind: arrived
task_id: action-test-001
detail: ''
value: 22.87434125099753
---
stamp:
  sec: 1793877634
  nanosec: 802071290
monotonic_sec: 17815.474592095
kind: completed
task_id: action-test-001
detail: ''
value: 0.0
---
# accepted 任务管理器接受了报警任务
# dispatched 任务被派发，准备向Nav2发送导航目标
# arrived Nav2导航成功，机器人到达位置
# completed 到达后预设的3s事件处理
```

## 2.4 Timer定时器

由于`mission_manager`不可能只在收到报警时才工作，它还需要持续状态，因此源码中用了一个50ms定时器，周期性调用`tick()`，理论上每秒执行20次，但实际执行频率受到系统调度和回调耗时影响。

看源码：`/patrol_robot_ws/src/patrol_manager/src/mission_node.cpp`中的`create_wall_timer()`

```c++
timer_=create_wall_timer(50ms,[this]{tick();});
/*
[this] 允许回调访问当前对象
tick() 每次定时触发时执行的成员函数
timer_ 保存定时器对象
*/

/*1.为什么能直接写50ms？
using namespace std::chrono_literals;允许使用50ms、100ms、1s这样的时间写法
*/

/*2.[this]{tick();}是什么？
这是一个Lambda回调函数，当定时器触发时，执行当前MissionNode对象的tick()函数
*/
```

小实验：
```
# 先观察定时器频率，20hz
donk@ubuntu:~$ ros2 topic hz /patrol/status 
average rate: 20.006
	min: 0.048s max: 0.053s std dev: 0.00126s window: 21

# 修改源码：timer_=create_wall_timer(100ms,[this]{tick();});
# 理论上频率为10hz
# 关闭终端，重新编译，重启
cd ~/patrol_robot_ws
colcon build --packages-select patrol_manager
source install/setup.bash
bash scripts/run.sh

# 修改成功，然后再将50改回去，重新编译
donk@ubuntu:~/patrol_robot_ws$ ros2 topic hz /patrol/status 
average rate: 10.005
	min: 0.094s max: 0.106s std dev: 0.00239s window: 22
```

## 2.5 c++业务逻辑

假设机器人正在巡逻，突然收到两个报警：
报警A：优先级20
报警B：优先级80
机器人先处理哪个？

### 2.5.1 源码

**`submit()`报警任务如何进入队列？**

```C++
known.insert(t.id); t.event=true; t.received=now; t.expires+=now;
t.order=++sequence; queue.push_back(t); record("accepted","",0,t.id);
return true;
// 第一行：保存任务信息
// event=true 标记这是报警事件任务，而不是普通巡逻任务
// received=now 记录任务进入系统的时间

// 第二行：放入任务队列
// queue.push_back(t) 
这里要提到std::vector<Task> queue;
// std::vector是C++动态数组，可以保存多个元素
// Task是在mission.hpp中自己定义的任务结构体
// push_back(t)将任务t添加到数组末尾

// 第三行：记录accepted
record("accepted","",0,t.id);// 代表报警任务已经被任务管理器接受，但accepted不等于机器人已经开始导航，表示任务成功进入系统
```

**`tick()`：如何从队列中选择任务？**

之前已经知道，`mission_node.cpp`隔50ms会调用`mission_->tick(t,healthy()&&nav_ready());`，接着看`missino.hpp`中真正的调度逻辑

```c++
// 1. 先检查是否可以执行任务
	// 如果机器人处于暂停状态/存在故障，暂时不调度新任务
if (paused || !fault.empty()) return;
	// 当前正在导航/系统尚未就绪，不发起导航
if (flying || !ready) return;
```

```c++
// 2. 从队列中取出任务
if (!active) {
  if (!queue.empty()) {
    auto it=best(); active=*it; queue.erase(it);
  } else {
    Task t; t.id="patrol/"+std::to_string(patrol_index);
    t.pose=cfg.waypoints.at(patrol_index); t.handling=cfg.patrol_dwell; active=t;
  }
}

// auto 让编译器自动推导变量类型
// best() 让队列中找出应该优先执行的任务
// *it 取得迭代器it指向的任务
// active=*it 将选中的任务设为当前任务
// queue.erase(it) 从等待队列中移除该任务

// 而这里引申出一个问题：best()怎么知道哪个任务优先？
	// 优先级不同：数字越大越优先（高优先级优先）
	// 优先级相同：先进入队列的任务优先（同优先级先进先出）
return a.priority!=b.priority ? a.priority>b.priority : a.order<b.order;
```

```c++
// 3. 生成任务执行指令
flying=true; started=now; ++token;
Effect e{}; e.kind=Effect::Start; e.task=*active; e.token=token; effects.push_back(e);
record("dispatched", "", active->event ? now-active->received : 0);
	// Effect::Start生成一条开始导航的执行指令
	// dispatched记录任务已经被派发
// 这条指令后续由mission_node.cpp读取，并调用Action学到的start()
```

### 2.5.2 任务优先级验证实验

```bash
# 终端 A：记录任务事件
ros2 topic echo /patrol/records

# 终端 B：暂停任务
ros2 service call /patrol/set_paused std_srvs/srv/SetBool "{data: true}"

# 先发优先级 20 的任务
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
'{id: demo-low-003, priority: 20, target: {header: {frame_id: map}, pose: {position: {x: 1.0, y: 1.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}'

# 再发优先级 80 的任务
ros2 topic pub --once /patrol/incidents patrol_interfaces/msg/Incident \
'{id: demo-high-003, priority: 80, target: {header: {frame_id: map}, pose: {position: {x: 7.0, y: 7.0}, orientation: {w: 1.0}}}, ttl_sec: 180.0, handling_sec: 3.0}'

# 确认暂停与任务排队
ros2 topic echo /patrol/status --once

# 尽快恢复，避免 180 秒 TTL 到期
ros2 service call /patrol/set_paused std_srvs/srv/SetBool "{data: false}"
```

- 第一轮 `test-low-001`、`test-high-001` 暂停等待过久：`queue_size: 2`，但两个任务分别在接受后约 180 秒记录 `expired`，`detail: pending TTL`，恢复时没有执行这两个报警。说明排队中的报警也会过期。
- 第二轮使用新 ID 并及时恢复：记录顺序为 `accepted low-002`、`accepted high-002`、`resumed`、`dispatched high-002`、`arrived high-002`、`completed high-002`、`dispatched low-002`、`arrived low-002`、`completed low-002`。真实验证了高优先级先执行。
- `handling_sec: 3.0` 对应到达后约 3 秒记录 `completed`；`id` 改成 `-002` 是为了避免重复 ID 被忽略。

## 2.6 ROS2整体调用链

场景：机器人正在巡逻 -> 收到报警 -> 前往报警位置 -> 到达 -> 处理3s -> 完成报警任务

## 2.6 整体调用链：Topic、Service、Action、Timer

### 2.6.1 主调用链：报警 → 导航 → 完成

```text
【Topic：接收报警】
mission_node.cpp → create_subscription()
    ↓ 收到 /patrol/incidents
mission.hpp → submit()
    ↓ accepted：报警入队

【Timer：任务调度】
mission_node.cpp → create_wall_timer(50ms)
    ↓ 周期执行 tick()
mission.hpp → tick()
    ↓ best() 选择优先级最高的任务
    ↓ dispatched：生成 Start 指令
mission_node.cpp → drain() / start()
    ↓ 取出指令，准备导航

【Action：执行导航】
mission_node.cpp → async_send_goal()
    ↓ 向 Nav2 发送导航目标
Nav2 → 执行导航
    ↓ 返回最终结果
mission_node.cpp → result_callback
    ↓ 调用 mission_->result()
mission.hpp → result()
    ↓ arrived：导航成功，进入事件处理阶段

【Timer：任务完成】
mission.hpp → tick()
    ↓ 处理时间结束
mission.hpp → finish()
    ↓ completed：报警任务完成
```

### 2.6.2 暂停与恢复调用链

```text
【Service：暂停】
终端 → /patrol/set_paused (true)
    ↓
mission_node.cpp → create_service() 回调
    ↓
mission.hpp → pause(true)
    ↓ paused = true
    ↓ 如果正在导航，生成 Cancel 指令
mission_node.cpp → tick() / drain()
    ↓ 调用 cancel()
Nav2 → 取消当前导航
    ↓ 返回导航终结结果
mission_node.cpp → result_callback
    ↓
mission.hpp → result()
    ↓ 将未完成的报警任务重新入队

【Service：恢复】
终端 → /patrol/set_paused (false)
    ↓
mission.hpp → pause(false)
    ↓ paused = false
mission_node.cpp → Timer → tick()
    ↓ 等待旧导航终结且满足调度条件
mission.hpp → tick()
    ↓ 重新选择任务，生成 Start 指令
mission_node.cpp → start()
    ↓ 向 Nav2 发送导航目标
```

### 2.6.3 核心函数职责

| 函数                    | 作用                       |
| ----------------------- | -------------------------- |
| `create_subscription()` | 接收报警 Topic             |
| `create_service()`      | 接收暂停、恢复请求         |
| `create_wall_timer()`   | 周期性驱动任务调度         |
| `submit()`              | 接收任务并加入队列         |
| `best()`                | 选择优先级最高的任务       |
| `tick()`                | 检查状态并决定任务调度     |
| `drain()`               | 取出待执行的指令           |
| `start()`               | 构造并发送导航目标         |
| `async_send_goal()`     | 异步请求 Nav2 导航         |
| `result_callback`       | 接收 Nav2 导航结果         |
| `result()`              | 更新导航结果对应的业务状态 |
| `finish()`              | 完成当前任务               |

**核心理解：**

- `mission_node.cpp`：负责 ROS2 通信、定时驱动和执行指令。
- `mission.hpp`：负责任务队列、优先级、状态机和调度决策。
- Nav2：负责实际导航，不负责决定报警任务优先级。

