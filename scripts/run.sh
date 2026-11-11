#!/usr/bin/env bash
set -eo pipefail
TASK_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
source /opt/ros/humble/setup.bash
if [[ ! -f "$TASK_ROOT/install/setup.bash" ]]; then
  echo 'Build first: bash scripts/setup_ubuntu.sh' >&2
  exit 1
fi
source "$TASK_ROOT/install/setup.bash"
exec python3 "$TASK_ROOT/tools/run_system.py" "$@"
