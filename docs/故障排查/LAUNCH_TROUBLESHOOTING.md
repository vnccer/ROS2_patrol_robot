# 启动时找不到 lightweight_sim

报错包含 `executable 'lightweight_sim' not found on the libexec directory .../install/patrol_sim/lib/patrol_sim`，说明包已经找到，但可执行入口未被识别。Windows 打包/复制丢失 Linux 执行位、配合 `--symlink-install`，会产生这个现象；符号链接本身不会为目标文件补上执行权限。

本次检查发现旧交付 ZIP 的该脚本模式为 `0100666`，没有执行位。三个入口都需处理。在用户实际的 Ubuntu 工程路径中运行：

```bash
cd ~/patrol_robot_ws
source /opt/ros/humble/setup.bash
chmod +x src/patrol_sim/scripts/{lightweight_sim,velocity_guard,control_panel}
colcon build --packages-select patrol_sim --symlink-install
source install/setup.bash
ros2 pkg executables patrol_sim
```

最后应列出 `control_panel`、`lightweight_sim`、`velocity_guard`。确认构建成功且三项都出现后，再运行 `bash scripts/run.sh`。如果仍缺少入口，查看 `ls -l install/patrol_sim/lib/patrol_sim/`，检查安装结果和符号链接是否存在，而不是反复重装依赖。

新的 CMake 安装规则会在构建目录准备三个入口副本，并显式赋予 `0755`；符号链接安装指向这些副本，避免依赖源码原本的执行权限。只复制源码到 Windows/VMware 共享文件夹而丢失执行位时，也能在原生 Ubuntu 构建目录中正确生成入口。该规则要求 CMake ≥ 3.19，Ubuntu 22.04 默认版本满足要求。

ZIP 打包器也改为保存 Unix 脚本执行权限。此修复不等于已经完成真实 ROS2/Nav2 端到端验收；以 Ubuntu 重建和运行结果为准。

依据：[ament 上游记录](https://github.com/ament/ament_cmake/issues/545)、[Humble 符号链接安装实现](https://github.com/ament/ament_cmake/blob/humble/ament_cmake_core/cmake/symlink_install/ament_cmake_symlink_install.cmake.in)。
