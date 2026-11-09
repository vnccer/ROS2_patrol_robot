# 复用来源与边界

本项目优先复用已有导航与机器人生态，业务调度核心和控制台在本项目中编写。没有把其他项目的完整任务调度器改名后当作原创实现。

| 来源 | 使用方式 | 版本与许可 |
|---|---|---|
| [Nav2 / navigation2](https://github.com/ros-navigation/navigation2/tree/humble) | 直接依赖其规划、控制、恢复行为、生命周期与 `NavigateToPose` action；借鉴显式取消与异步结果处理方式 | ROS2 Humble；包内许可分别声明，`nav2_bringup` 为 Apache-2.0 |
| [nav2_bringup 的参数](https://github.com/ros-navigation/navigation2/blob/humble/nav2_bringup/params/nav2_params.yaml) | 原始快照在 `third_party/nav2_params.humble.yaml`；`tools/generate_assets.py` 生成修改版 `config/nav2.yaml` | blob `81dfc981a83c8372da4e4744c4f6cbf4002d2f5b`；Apache-2.0 |
| [ROBOTIS TurtleBot3 仿真](https://github.com/ROBOTIS-GIT/turtlebot3_simulations/tree/humble) | Gazebo 模式直接引用安装包中的 Burger 模型、机器人 TF launch 和生成 launch；没有复制其模型资源 | Humble；Apache-2.0，Copyright ROBOTIS CO., LTD. / Open Source Robotics Foundation（见各上游文件） |
| [官方生成脚本](https://github.com/ROBOTIS-GIT/turtlebot3_simulations/blob/humble/turtlebot3_gazebo/launch/spawn_turtlebot3.launch.py) | 核对 `x_pose/y_pose`、模型资源路径和启动方式 | blob `8d386034fccf57823594065f052a40b32aecfe99` |

保留的 Nav2 原始参数快照未修改。派生配置文件头标注了修改日期与内容；完整 Apache-2.0 许可见 `LICENSE`。地图、世界与轻量底盘由本项目生成；轻量模式使用理想地图定位，Gazebo 模式使用 AMCL。两者都调用真正的 Nav2，不自行重写规划器。

Humble 上游用于核对 action 的文件：[NavigateToPose.action](https://github.com/ros-navigation/navigation2/blob/humble/nav2_msgs/action/NavigateToPose.action)，blob `b7077922418325bcea5f994c24f3955c43daa22a`。本项目遵循其 Humble 接口，没有混用 Rolling 的返回字段。

安装脚本使用 Ubuntu/ROS 软件包管理器安装二进制依赖，不固定整个操作系统的依赖快照；执行后会在 `test_results/installed_ros_packages.txt` 记录实际安装版本。浏览器本机预览的 A* 是教学预览组件，其结果不作为 Nav2 或 Gazebo 验收结果。
