#!/usr/bin/env bash
set -euo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
PATROL_INSTALL_GAZEBO=false
PATROL_ROSDEP_MIRROR=false
for argument in "$@"; do
  case "$argument" in
    --gazebo) PATROL_INSTALL_GAZEBO=true ;;
    --rosdep-mirror) PATROL_ROSDEP_MIRROR=true ;;
    *) echo "Unknown option: $argument (use --gazebo and/or --rosdep-mirror)" >&2; exit 1 ;;
  esac
done

# Only replace the GitHub rosdistro prefix; retain custom entries and keep a backup.
configure_rosdep_mirror() {
  local task_list
  task_list="$(mktemp)"
  if [[ -s /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
    cat /etc/ros/rosdep/sources.list.d/20-default.list > "$task_list"
  elif ! curl --fail --location --retry 2 --connect-timeout 10 --max-time 60 \
      https://mirrors.ustc.edu.cn/rosdistro/rosdep/sources.list.d/20-default.list \
      --output "$task_list"; then
    rm -f -- "$task_list"
    return 1
  fi
  sed -i 's|https\?://raw.githubusercontent.com/ros/rosdistro/master|https://mirrors.ustc.edu.cn/rosdistro|g' "$task_list"
  if ! grep -q '^yaml https://mirrors.ustc.edu.cn/rosdistro/rosdep/' "$task_list"; then
    echo 'Mirror sources list is invalid; leaving system configuration untouched.' >&2
    rm -f -- "$task_list"
    return 1
  fi
  sudo install -d /etc/ros/rosdep/sources.list.d
  if [[ -e /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
    sudo cp -n /etc/ros/rosdep/sources.list.d/20-default.list \
      /etc/ros/rosdep/sources.list.d/20-default.list.patrol.bak
  fi
  sudo install -m 644 "$task_list" /etc/ros/rosdep/sources.list.d/20-default.list
  rm -f -- "$task_list"
  export ROSDISTRO_INDEX_URL=https://mirrors.ustc.edu.cn/rosdistro/index-v4.yaml
}
source /etc/os-release
if [[ "${ID}" != ubuntu || "${VERSION_ID}" != 22.04 ]]; then
  echo 'This setup targets Ubuntu 22.04 + ROS2 Humble.' >&2
  exit 1
fi
if [[ ! -f /opt/ros/humble/setup.bash ]]; then
  echo 'Install ROS2 Humble first: docs/ENVIRONMENT.md' >&2
  exit 1
fi
sudo apt-get update
sudo apt-get install -y curl build-essential python3-colcon-common-extensions python3-rosdep \
  python3-yaml python3-pytest ros-humble-navigation2 ros-humble-nav2-bringup \
  ros-humble-rviz2 ros-humble-robot-state-publisher
if [[ "$PATROL_INSTALL_GAZEBO" == true ]]; then
  sudo apt-get install -y ros-humble-gazebo-ros-pkgs ros-humble-turtlebot3-gazebo \
    ros-humble-turtlebot3-description
fi
# ROS environment scripts can reference unset shell variables.
set +u
source /opt/ros/humble/setup.bash
set -u
if [[ "$PATROL_ROSDEP_MIRROR" == true ]]; then
  configure_rosdep_mirror
elif [[ ! -s /etc/ros/rosdep/sources.list.d/20-default.list ]]; then
  if ! sudo -E rosdep init; then
    echo 'GitHub initialization failed; retrying with the USTC rosdistro mirror.'
    configure_rosdep_mirror
  fi
fi
if grep -Eq '^[[:space:]]*gbpdistro[[:space:]].*fuerte[.]yaml([[:space:]]|$)' \
    /etc/ros/rosdep/sources.list.d/20-default.list; then
  # The default list still contains a legacy ROS1 Fuerte source. This workspace is Humble-only.
  sudo cp -n /etc/ros/rosdep/sources.list.d/20-default.list \
    /etc/ros/rosdep/sources.list.d/20-default.list.patrol-before-fuerte.bak
  sudo sed -i -E '/^[[:space:]]*gbpdistro[[:space:]].*fuerte[.]yaml([[:space:]]|$)/s/^/# Disabled for Humble: /' \
    /etc/ros/rosdep/sources.list.d/20-default.list
fi
if grep -q '^yaml https://mirrors.ustc.edu.cn/rosdistro/' /etc/ros/rosdep/sources.list.d/20-default.list; then
  export ROSDISTRO_INDEX_URL=https://mirrors.ustc.edu.cn/rosdistro/index-v4.yaml
fi
if ! rosdep update --rosdistro humble; then
  echo 'rosdep update failed; retrying with the USTC rosdistro mirror.'
  configure_rosdep_mirror
  rosdep update --rosdistro humble
fi
cd "$TASK_ROOT"
rosdep install --from-paths src --ignore-src --rosdistro humble -r -y
colcon build --symlink-install --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
colcon test --event-handlers console_direct+
colcon test-result --verbose
python3 tools/build_core.py
python3 -m pytest tests -q
mkdir -p test_results
dpkg-query -W 'ros-humble-*' > test_results/installed_ros_packages.txt
echo 'Ready: bash scripts/run.sh'
