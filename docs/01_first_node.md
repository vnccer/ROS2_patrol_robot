# 第 1 次实操：运行自己的节点

本次目标：让自己编写的 `patrol_node` 启动、打印一句日志，并出现在 ROS2 节点列表中。这是后续巡逻任务管理节点的起点。

代码参考教材第 2 章的节点与面向对象写法，以及第 3.3 节的 C++ 节点组织方式：节点类保存功能，构造函数负责初始化，`main()` 负责启动和退出。

## 1. 在 Ubuntu 打开工程

将 Windows 中整个 `patrol_robot_ws` 文件夹复制到 Ubuntu 用户主目录，然后在 Ubuntu 终端执行：

```bash
cd ~/patrol_robot_ws
code .
```

在 VSCode 打开 `src/patrol_manager/src/patrol_node.cpp`。可以对照 Windows 中的参考文件，在 Ubuntu 副本中逐行重新输入代码。`CMakeLists.txt` 和 `package.xml` 这次先使用现成内容。

## 2. 理解代码的执行顺序

程序从 `main()` 开始执行，类定义本身不会启动一个节点。

```text
rclcpp::init()
    ↓
std::make_shared<PatrolNode>("patrol_node")
    ↓
进入 PatrolNode 构造函数，初始化父类 Node 并输出日志
    ↓
rclcpp::spin(node) 等待并处理回调
    ↓
按 Ctrl+C 请求停止，spin 返回
    ↓
rclcpp::shutdown()，main 返回
```

对照源码理解这几处就够了：

| 代码 | 本次需要理解的含义 |
|---|---|
| `class PatrolNode : public rclcpp::Node` | 定义自己的节点类，继承 ROS2 节点的能力。 |
| `PatrolNode(...) : Node(node_name)` | 创建对象时调用构造函数，并先用名称初始化父类节点。 |
| `const std::string &node_name` | 用只读引用接收节点名称。 |
| `RCLCPP_INFO(...)` | 通过节点的日志器输出一条 INFO 日志。 |
| `std::make_shared<PatrolNode>(...)` | 创建节点对象，交给共享智能指针管理。 |
| `rclcpp::spin(node)` | 持续等待并处理回调，直到收到退出请求。 |

现在还没有添加自己的定时器或订阅回调，所以启动日志只出现一次。它位于构造函数中，`spin()` 不会反复执行构造函数。

## 3. 编译并运行

以下命令都在 Ubuntu 终端执行。先保存源码，再编译：

```bash
source /opt/ros/jazzy/setup.bash
cd ~/patrol_robot_ws
colcon build --packages-select patrol_manager --symlink-install
```

编译成功后，在同一个终端执行：

```bash
source install/setup.bash
ros2 run patrol_manager patrol_node
```

正常情况下，日志包含：

```text
[INFO] [...] [patrol_node]: Patrol node started.
```

终端会保持被程序占用，这是 `spin()` 正在运行。

保持该终端运行，在 Ubuntu 的另一个终端检查：

```bash
source /opt/ros/jazzy/setup.bash
source ~/patrol_robot_ws/install/setup.bash
ros2 node list
```

结果中应包含 `/patrol_node`。回到运行节点的终端，按 `Ctrl+C` 退出。

这里有三个名称：`patrol_manager` 是功能包名，`ros2 run` 后的 `patrol_node` 是可执行程序名，节点列表中的 `/patrol_node` 来自 C++ 中传入的节点名称。后两者这次取了相同的名字，但含义不同。

## 4. 做一个小修改

把源码中的 `Patrol node started.` 改成 `My patrol node is running.`，保存后重新编译、运行。确认终端显示新文字。

先能说清楚两件事即可：哪一行创建了节点对象，以及为什么日志只打印一次。遇到错误时，把执行的命令和完整报错贴过来，我们根据实际结果排查。

## 遇到启动问题时

- 提示 `colcon: command not found`：Ubuntu 尚未安装构建工具，可执行 `sudo apt install python3-colcon-common-extensions`，再重试编译。
- 提示找不到 `patrol_manager`：先确认编译成功，再在当前终端执行 `source ~/patrol_robot_ws/install/setup.bash`。
- 修改后仍是旧日志：先退出旧节点，确认修改的是 Ubuntu 工程中的源码，再重新编译并启动。

`package.xml` 中的维护者与许可证目前是占位信息，可在准备对外发布时按你的选择填写。

参考：[ROS2 Jazzy C++ 节点示例](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Tutorials/Beginner-Client-Libraries/Writing-A-Simple-Cpp-Publisher-And-Subscriber.rst)、[ament_cmake 官方说明](https://github.com/ros2/ros2_documentation/blob/jazzy/source/How-To-Guides/Ament-CMake-Documentation.rst)。
