#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "${BMOS_LAB:?Set BMOS_LAB to the private lab}"
mkdir -p runtime/terminal-fast/io
chmod 700 runtime/terminal-fast runtime/terminal-fast/io
[[ ${1:-gpu} == gpu || ${1:-gpu} == software ]]
exec systemd-run --user --unit=os-evolution-terminal --collect \
  -p MemoryMax=3G -p MemorySwapMax=0 -p CPUQuota=200% -p TasksMax=128 \
  -p TimeoutStopSec=30 -p KillMode=control-group \
  -p LimitFSIZE=14G -p Nice=10 --setenv="BMOS_LAB=$PWD" \
  /bin/bash "$source_dir/launch.sh" "${1:-gpu}"
