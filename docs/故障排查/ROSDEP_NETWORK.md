# rosdep 网络与旧 Fuerte 条目

## Humble 已更新，但 fuerte.yaml 下载失败

如果 `base.yaml/python.yaml/ruby.yaml` 和 Humble 索引已经成功，唯一失败的是 `releases/fuerte.yaml`，原因是默认列表还包含旧 ROS1 Fuerte 的 `gbpdistro` 条目。`--rosdistro humble` 过滤发行版索引，不会免除这个独立来源的下载。该条目不是本项目的 Humble 依赖。

在 Ubuntu 中可以原地注释它，不用重新复制工程：

```bash
sudo sed -i.before-fuerte-fix -E \
  '/^[[:space:]]*gbpdistro[[:space:]].*fuerte[.]yaml([[:space:]]|$)/s/^/# Disabled for Humble: /' \
  /etc/ros/rosdep/sources.list.d/20-default.list
export ROSDISTRO_INDEX_URL=https://mirrors.ustc.edu.cn/rosdistro/index-v4.yaml
rosdep update --rosdistro humble
```

第一条命令保留 `.before-fuerte-fix` 备份。确认更新结束没有 `ERROR` 后，在工程目录重新执行 `bash scripts/setup_ubuntu.sh --rosdep-mirror`，它会保留已注释的条目并继续安装/构建；Gazebo 加 `--gazebo`。

本地安装脚本已增加自动识别、备份并注释这一条目的逻辑。仅处理 `20-default.list` 的 Fuerte `gbpdistro` 行，其余规则和自定义源保留。依据：[上游默认列表](https://github.com/ros/rosdistro/blob/master/rosdep/sources.list.d/20-default.list)。

## GitHub 连接重置

如果 apt 的 fontconfig 触发器已处理，随后 `sudo rosdep init` 在下载 `raw.githubusercontent.com/.../20-default.list` 时发生 `Connection reset by peer`，失败阶段是依赖数据库初始化。先前 apt 安装无需撤销；这段日志没有显示源码编译失败。

更新本地脚本后，在 Ubuntu 工作空间中重新执行：

```bash
bash scripts/setup_ubuntu.sh --rosdep-mirror
```

需要 Gazebo 则同时传入 `--gazebo`。apt 会保留已安装的软件包，脚本继续配置 rosdep、构建和测试。

安装脚本的镜像模式同时替换默认 sources list 中的 rosdistro URL 与 `ROSDISTRO_INDEX_URL`，避免只修好 init 而 update 仍访问 GitHub。保留已有自定义条目，并在修改前保留一份 `20-default.list.patrol.bak`；不修改用户 `.bashrc`。后续单独运行 `rosdep update` 时，在同一终端先执行：

```bash
export ROSDISTRO_INDEX_URL=https://mirrors.ustc.edu.cn/rosdistro/index-v4.yaml
rosdep update --rosdistro humble
```

没有同步新脚本时，可在 Ubuntu 用以下命令手动初始化。下载成功后才安装配置，避免失败下载覆盖原文件：

```bash
curl -fL --retry 2 --connect-timeout 10 --max-time 60 \
  https://mirrors.ustc.edu.cn/rosdistro/rosdep/sources.list.d/20-default.list \
  -o /tmp/patrol-rosdep-default.list
# 上一条成功后再继续
sed -i 's|https\?://raw.githubusercontent.com/ros/rosdistro/master|https://mirrors.ustc.edu.cn/rosdistro|g' /tmp/patrol-rosdep-default.list
sed -i -E '/^[[:space:]]*gbpdistro[[:space:]].*fuerte[.]yaml([[:space:]]|$)/s/^/# Disabled for Humble: /' /tmp/patrol-rosdep-default.list
sudo install -d /etc/ros/rosdep/sources.list.d
if [ -e /etc/ros/rosdep/sources.list.d/20-default.list ]; then
  sudo cp -n /etc/ros/rosdep/sources.list.d/20-default.list /etc/ros/rosdep/sources.list.d/20-default.list.patrol.bak
fi
sudo install -m 644 /tmp/patrol-rosdep-default.list /etc/ros/rosdep/sources.list.d/20-default.list
export ROSDISTRO_INDEX_URL=https://mirrors.ustc.edu.cn/rosdistro/index-v4.yaml
rosdep update --rosdistro humble
```

看到更新成功后，在当前终端重新运行原安装脚本。更新使用普通用户，不要运行 `sudo rosdep update`。

依据：[USTC rosdistro 镜像说明](https://mirrors.ustc.edu.cn/help/rosdistro.html)。本次检查了 Bash 语法与镜像说明；没有远程操作 Ubuntu 虚拟机或声称其网络已恢复。
