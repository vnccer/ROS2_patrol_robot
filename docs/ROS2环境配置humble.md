# 当前项目的 Humble 环境

运行环境为 Windows + VMware + Ubuntu 22.04 + ROS2 Humble，Ubuntu 工程目录为 `~/patrol_robot_ws`。

- [环境安装说明](patrol_robot_ws/docs/ENVIRONMENT.md)：Ubuntu、Humble 和项目依赖。
- [项目 README](patrol_robot_ws/README.md)：项目功能、Windows/Linux 操作、踩坑命令、知识图谱。
- [实验菜单](patrol_robot_ws/docs/EXPERIMENTS.md)：参数改动、警报抢占、故障注入和指标统计。

已有 Humble 环境时，在 Ubuntu 的工程目录安装并启动：

```bash
cd ~/patrol_robot_ws
bash scripts/setup_ubuntu.sh --rosdep-mirror
bash scripts/run.sh
```

日常运行只需要最后一条命令。环境与操作说明统一维护在以上文档。
