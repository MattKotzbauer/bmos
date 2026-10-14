#!/usr/bin/env bash
set -euo pipefail
[[ $(cat /etc/os-evolution-guest) == arch-baseline ]]
export CODEX_HOME=/home/matt/.codex-daily
export XDG_STATE_HOME=/home/matt/.local/state/bmos-daily
export HTTPS_PROXY=http://127.0.0.1:18080 HTTP_PROXY=http://127.0.0.1:18080
export NO_PROXY=localhost,127.0.0.1
export PATH=/home/matt/.local/bin:/home/matt/.bun/bin:/usr/local/bin:/usr/bin:/bin
mkdir -p "$XDG_STATE_HOME" /home/matt/.local/share/bmos/daily-resurrect
if ! tmux -L bmos-daily has-session -t daily 2>/dev/null; then
  tmux -L bmos-daily new-session -d -s daily -n notes -c /home/matt/thing
  tmux -L bmos-daily set-option -g @resurrect-dir /home/matt/.local/share/bmos/daily-resurrect
fi
exec tmux -L bmos-daily attach-session -t daily
