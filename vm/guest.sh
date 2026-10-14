#!/usr/bin/env bash
set -euo pipefail
cd "${BMOS_LAB:?Set BMOS_LAB to the private lab}"
terminal_options=()
if [[ ${1:-} == --tty ]]; then terminal_options=(-t); shift; fi
exec ssh "${terminal_options[@]}" -F /dev/null -i private/arch-guest-key \
  -o IdentitiesOnly=yes -o ForwardAgent=no -o ForwardX11=no \
  -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=private/terminal-known-hosts \
  -o ControlMaster=auto -o ControlPersist=600 \
  -o "ControlPath=$PWD/runtime/terminal-fast/control" \
  -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
  -o "ProxyCommand=socat STDIO UNIX-CONNECT:$PWD/runtime/terminal-fast/io/ssh.sock" \
  matt@terminal-evolution "export PATH=/home/matt/.local/bin:/home/matt/.bun/bin:/usr/local/bin:/usr/bin:/bin; export DISPLAY=:0 XAUTHORITY=/home/matt/.Xauthority LANG=en_US.UTF-8; $*"
