# 移动机器人巡检与事件响应

这是项目的起点：一个最小的 C++ ROS2 节点。当前程序只输出启动日志，然后等待回调；后续在这个工程中逐步增加功能。

开发环境按已有笔记使用 Ubuntu 24.04 + ROS2 Jazzy。编译、运行命令均在 VMware 的 Ubuntu 终端执行。

## 从这里开始

把整个 `patrol_robot_ws` 文件夹复制到 Ubuntu 用户主目录，使工程路径为 `~/patrol_robot_ws`。先打开 [第 1 次实操：运行自己的节点](docs/01_first_node.md)，按步骤手敲、编译和观察结果。

```text
patrol_robot_ws/                 ROS2 工作空间
├── README.md
├── .gitignore
├── docs/
│   └── 01_first_node.md          本次实操说明
└── src/
    └── patrol_manager/          ROS2 功能包
        ├── CMakeLists.txt       编译和安装规则
        ├── package.xml          功能包信息与依赖
        └── src/
            └── patrol_node.cpp 节点参考代码
```

## 直接编译运行

在 Ubuntu 新开一个终端：

```bash
source /opt/ros/jazzy/setup.bash
cd ~/patrol_robot_ws
colcon build --packages-select patrol_manager --symlink-install
source install/setup.bash
ros2 run patrol_manager patrol_node
```

预期输出包含 `Patrol node started.`，随后程序保持运行。按 `Ctrl+C` 退出。

本目录中的源码是手敲时的参考。修改 Ubuntu 副本中的 C++ 代码后，需要重新编译，再启动节点。

## 当前验证范围

已在 Windows 侧核对功能包结构、XML 与编译配置；尚未在 Ubuntu/ROS2 中实际编译和运行。运行结果以你在虚拟机中的实操为准。
