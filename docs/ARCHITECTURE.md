# 设计与接口

## 任务与导航是两层状态

业务核心 `Mission` 持有巡逻索引、当前任务、队列和控制开关。ROS 层持有 Nav2 action handle。单线程执行器串行触发回调，核心产生 `Start`、`Cancel`、`Record` 三类效果，由 ROS 层执行。

```text
WAITING → PATROLLING → DWELLING → 下一巡逻点
             ↓ 高优先级事件
         CANCELLING → RESPONDING → HANDLING_EVENT
                          ↑               ↓ 完成
                          └── 队列事件 / 未完成巡逻点
```

`PAUSED` 和 `FAULT` 是独立的许可条件。显示优先级为故障、暂停、取消、处置、导航、等待；显示 `FAULT` 时底层仍可能等待旧 action 的终结结果。

## 抢占和恢复

- 事件优先级 1～100，巡逻为 0；严格更高才抢占，同级 FIFO。
- 一次最多一个导航目标。先关闭许可，发取消请求，等终结结果，再派发。取消服务答复不代表导航已经结束。
- 每次派发带递增 token，旧结果不能完成新任务。等待目标接收答复时发生抢占，会在取得 handle 后立即取消。
- 取消超过 3 秒未终结会锁存故障；不清空旧 handle，也不并发新目标。迟到终结结果收到后可恢复；永久失联时需要重启整套仿真清理孤立任务。
- 巡逻点仅在抵达并停留完成后前进。事件完成/失败后重新导航到被中断的点，不沿用旧路径。
- 处置被抢占/暂停后重新排队；恢复时重新导航并从头计时，等待 TTL 可能在期间过期。
- 去重 ID 在进程内最多保留 10000 个，满后拒绝新 ID。队列最多接收 64 个等待任务，被中断的当前事件可额外占一个恢复槽位。
- 导航默认重试一次。事件最终失败后继续其他任务；巡逻点最终失败锁存故障，恢复后重试原点，不静默跳过。

## 时间与保护

Nav2、传感器、TF 使用 ROS 时间；Gazebo 加载 `/clock`，轻量后端使用系统 ROS 时间。任务 TTL、目标/取消期限和健康检查使用单调时钟。CSV 同时记录两种时间。

暂停 Gazebo 时 ROS 时间可能停止，任务与保护时钟仍运行，因此会触发传感器故障；继续物理仿真后需要解除故障。这与任务的人工暂停不同。

Nav2 controller 经 velocity_smoother 进入 `/nav_cmd_vel`，恢复行为也进入该话题；只有 `velocity_guard` 发布 `/cmd_vel`。许可、导航速度、里程计、激光任意一项超过 0.5 秒未刷新，就每 50ms 发零速度。门禁用 steady timer，Gazebo 暂停不会冻结它。

任务管理器里程计超过 1 秒未刷新、Nav2 生命周期/服务失联时会故障。`recover` 要求里程计新鲜、Nav2 激活、旧目标已终结，且保留人工暂停。激光恢复是速度门禁的条件；若任务已因导航失败进入故障，也需人工恢复。

这些用于软件仿真验证。轻量底盘自身另有 0.5 秒指令超时；不能把软件机制直接当作真机急停硬件。

## ROS 接口

| 类型 | 名称 | 含义 |
|---|---|---|
| Topic / Incident | `/patrol/incidents` | map 坐标、单位四元数；ID 不得以 `patrol/` 开头 |
| Topic / MissionStatus | `/patrol/status` | 当前任务、队列、索引、计数、故障和许可 |
| Topic / TaskRecord | `/patrol/records` | 接收、去重、抢占、到达、完成、失败等 |
| Topic / Bool | `/patrol/motion_permit` | 心跳式速度许可 |
| Action / NavigateToPose | `/navigate_to_pose` | Nav2 目标、取消、结果 |
| Service / SetBool | `/patrol/set_paused` | 人工暂停，答复不等于底盘已静止 |
| Service / Trigger | `/patrol/emergency_stop` | 锁存操作员故障 |
| Service / Trigger | `/patrol/recover` | 健康满足后解除故障 |
| Service / SetBool | `/patrol/sim/drop_odom`、`drop_scan`、`blocked` | 轻量底盘故障注入 |

将传感器/视觉警报转换为 `Incident` 即可扩展事件来源。将模拟处置替换为真实 action 时，需增加开始、取消、结果接口，保留终结确认原则。控制台只绑定 loopback，跨设备访问可用 SSH 隧道。
