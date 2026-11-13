# 当前项目运行环境

当前项目使用 Windows + VMware + Ubuntu 22.04 + ROS2 Humble。Windows 本机预览与 Ubuntu 完整 ROS2 系统的区别、启动命令和操作方式统一见 [README](../../README.md)。

如果已经安装 Humble，直接从第 3 节准备本项目；无需重装 ROS。

## 1. 准备 Ubuntu

使用 Ubuntu 22.04（Jammy）。在 Ubuntu 终端确认：

```bash
lsb_release -a
```

VMware 建议先使用 NAT 网络，仿真性能不足时关闭 RViz 或 Gazebo GUI。源码放到 Ubuntu 用户目录 `~/patrol_robot_ws`，避免直接在共享文件夹运行构建产物。

## 2. 准备系统与 ROS 软件源

以下命令在新虚拟机的 Ubuntu 终端分段执行，遇到报错先停在对应步骤。

```bash
sudo apt update
sudo apt install -y locales software-properties-common curl
sudo locale-gen en_US en_US.UTF-8
sudo update-locale LC_ALL=en_US.UTF-8 LANG=en_US.UTF-8
export LANG=en_US.UTF-8
sudo add-apt-repository universe
```

使用官方当前推荐的 `ros2-apt-source` 软件包配置密钥和 ROS 软件源：

```bash
ROS_APT_SOURCE_VERSION=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | grep -F '"tag_name"' | awk -F'"' '{print $4}')
echo "$ROS_APT_SOURCE_VERSION"
```

应输出非空的版本号。随后下载并安装对应 Jammy 的源配置包：

```bash
curl -fL -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ROS_APT_SOURCE_VERSION}/ros2-apt-source_${ROS_APT_SOURCE_VERSION}.jammy_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt upgrade
```

新装 Ubuntu 22.04 应先完成系统升级，再安装 ROS2。如果升级提示重启，先重启，再继续下一步。

### 安装并检查 Humble

```bash
sudo apt install -y ros-humble-desktop ros-dev-tools
source /opt/ros/humble/setup.bash
echo "$ROS_DISTRO"
```

最后应输出 `humble`。为了让以后新开的 Bash 终端自动加载 Humble，将下面这一行添加到新虚拟机的 `~/.bashrc` 末尾一次：

```bash
source /opt/ros/humble/setup.bash
```

这里是编辑文件加入一行；当前终端也可手动执行这一行。当前终端只加载 Humble 和本工作空间的 `setup.bash`。

## 3. 安装和运行当前项目

把整个 `patrol_robot_ws` 复制到 Ubuntu 用户目录，保留 `src`、`scripts`、`tools`、`docs` 和配置资源。Windows 的编译产物、缓存以及其他环境的 `build/install/log` 无需复制。

```bash
cd ~/patrol_robot_ws
bash scripts/setup_ubuntu.sh --rosdep-mirror
bash scripts/run.sh
```

已经完成安装构建后，日常只运行 `bash scripts/run.sh`。需要 Gazebo 时：

```bash
bash scripts/setup_ubuntu.sh --rosdep-mirror --gazebo
bash scripts/run.sh backend:=gazebo gui:=false
```

网页控制台在 Ubuntu 浏览器打开 `http://127.0.0.1:8765`。具体实验见 [EXPERIMENTS.md](../实验与验证/EXPERIMENTS.md)，已遇到的问题见 [rosdep 网络恢复](../故障排查/ROSDEP_NETWORK.md) 与 [启动入口排障](../故障排查/LAUNCH_TROUBLESHOOTING.md)。

当前 [C++ 实践训练](../设计与路线/ROS2自主巡检项目_C++实践训练路线.md) 和后期 [安全性与稳定性开发](../设计与路线/ROS2自主巡检项目_安全性与稳定性开发路线.md) 均以真实 Nav2 + 轻量底盘为主，不要求安装 Gazebo 或接真机。SROS2 是后期选做实验，届时单独核实 RMW 和安全材料；完成环境安装不代表后续功能已经实现或验收。

依据：[Humble 官方 Ubuntu 安装说明](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)、[官方软件源配置步骤](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/_Apt-Repositories.rst)。本机静态检查和 Ubuntu 实际验收的边界见 [VALIDATION.md](../实验与验证/VALIDATION.md)。
