# 当前项目的 Humble 环境

运行环境为 Windows + VMware + Ubuntu 22.04 + ROS2 Humble，Ubuntu 工程目录为 `~/patrol_robot_ws`。

- [环境安装说明](ENVIRONMENT.md)：Ubuntu、Humble 和项目依赖。
- [项目 README](../README.md)：项目功能、Windows/Linux 操作、开发阶段、知识图谱。
- [实验菜单](EXPERIMENTS.md)：参数改动、警报抢占、故障注入和指标统计。
- [C++ 实践训练路线](ROS2自主巡检项目_C++实践训练路线.md)：当前任务 1～9。
- [安全性与稳定性开发路线](ROS2自主巡检项目_安全性与稳定性开发路线.md)：完成训练后的任务 10～18及选做任务 19。

已有 Humble 环境时，在 Ubuntu 的工程目录安装并启动：

```bash
cd ~/patrol_robot_ws
bash scripts/setup_ubuntu.sh --rosdep-mirror
bash scripts/run.sh
```

日常运行只需要最后一条命令。环境与操作说明统一维护在以上文档。

训练与后续开发默认使用真实 Nav2 + 轻量仿真；安全性与稳定性属于后期目标，按逐项验收推进。Gazebo 与 SROS2 均不作为当前 C++ 训练的环境前置。
