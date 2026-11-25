# 虚拟机

vmware + ubuntu-22.04.5-desktop-amd64.iso（[Ubuntu 22.04 LTS (Jammy Jellyfish)](https://releases.ubuntu.com/22.04/)）

```
账户：ubuntu
密码：123

机子名：ubuntu
账户：donk
密码：123

cpu和核心数都改成1，这样输入延迟小

在*.vmx文件添加
keyboard.vusb.enable = "TRUE"

# 下面操作不确定是否好用
sudo nano /etc/default/grub 将 "quiet splash" 修改为 "quiet splash nomodeset"
```

# ubuntu 环境

更新ubuntu，安装VMware Tools、梯子

```
sudo apt update
sudo apt upgrade -y

# 安装vmware-tools
sudo apt install open-vm-tools open-vm-tools-desktop -y

# 重启 vmtools 服务
sudo systemctl restart vmtoolsd

# 设置开机自启
sudo systemctl enable open-vm-tools.service

# 让字体更好看
sudo apt install gnome-tweaks
gnome-tweaks

# 安装ikuuu
sudo apt install ./ikuuu_vpn-0.17.5-22a756ce-linux-amd64.deb

# 配置代理
nano ~/.bashrc
# 开启代理
proxyon() {
    export http_proxy=http://127.0.0.1:7890
    export https_proxy=http://127.0.0.1:7890
    export HTTP_PROXY=$http_proxy
    export HTTPS_PROXY=$https_proxy
    echo "Proxy ON"
}
# 关闭代理
proxyoff() {
    unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
    echo "Proxy OFF"
}

source ~/.bashrc

# 检查代理是否成功
curl -s https://ipinfo.io/json
```

# ROS2环境（清华源）

适用于新装的 Ubuntu 22.04（jammy），安装 ROS2 Humble。本节采用手动配置清华源，与 [Humble 环境说明](ENVIRONMENT.md) 中的官方源安装方式二选一，无需重复配置软件源。

```bash
# 1. 安装必要工具
sudo apt update
sudo apt install -y curl gnupg software-properties-common
sudo add-apt-repository -y universe

# 2. 下载 ROS2 仓库签名公钥
curl -fsSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
  | gpg --dearmor \
  | sudo tee /usr/share/keyrings/ros-archive-keyring.gpg > /dev/null

# 3. 添加清华 ROS2 镜像源
echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://mirrors.tuna.tsinghua.edu.cn/ros2/ubuntu jammy main" \
  | sudo tee /etc/apt/sources.list.d/ros2.list

# 4. 备份 Ubuntu 软件源配置（保留首次备份）
sudo cp -n /etc/apt/sources.list /etc/apt/sources.list.bak

# 5. 将 Ubuntu 软件源切换为清华镜像（保留官方安全更新源）
sudo sed -i -E 's|https?://([a-zA-Z0-9.-]+\.)?archive\.ubuntu\.com/ubuntu/?|https://mirrors.tuna.tsinghua.edu.cn/ubuntu/|g' /etc/apt/sources.list

# 6. 更新软件包索引，并在安装 ROS2 前升级系统
sudo apt update
sudo apt upgrade -y

# 7. 安装 ROS2 Humble 桌面版、开发工具和海龟模拟器
sudo apt install -y ros-humble-desktop ros-dev-tools ros-humble-turtlesim

# 8. 加载 ROS2 环境
source /opt/ros/humble/setup.bash
echo "$ROS_DISTRO"  # 应输出 humble

# 9. 设置新终端自动加载 ROS2（避免重复添加）
grep -qxF 'source /opt/ros/humble/setup.bash' ~/.bashrc \
  || echo 'source /opt/ros/humble/setup.bash' >> ~/.bashrc

# 10. 验证 ROS2：在当前终端运行发布节点
ros2 run demo_nodes_cpp talker
```

另一终端执行：

```bash
source /opt/ros/humble/setup.bash
ros2 run demo_nodes_cpp listener
```

看到发布端持续输出 `Publishing`、接收端持续输出 `I heard`，说明基础通信正常。分别按 `Ctrl+C` 退出。

参考：[清华 ROS2 镜像配置](https://mirrors.tuna.tsinghua.edu.cn/help/ros2/)、[清华 Ubuntu 镜像配置](https://mirrors.tuna.tsinghua.edu.cn/help/ubuntu/)、[Humble 官方安装说明](https://github.com/ros2/ros2_documentation/blob/humble/source/Installation/Ubuntu-Install-Debs.rst)。以上为文档修改，尚未在新虚拟机中执行验证。

# 基础认知

ROS（Robot Operating System, 机器人操作系统） 
RMW（ROS Middleware Interface，ROS中间件接口）
RCL（ROS 2 Client Library，ROS2客户端库）
DDS（Data Distribution Service，数据分发服务）
RTPS（Real-time Publish-Subscribe，实时发布订阅协议）
