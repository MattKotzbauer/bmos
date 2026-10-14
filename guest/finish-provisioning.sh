#!/usr/bin/env bash
# Only after cloud-init has provisioned this disposable guest and network config.
set -euo pipefail
[[ $(cat /etc/os-evolution-guest) == arch-baseline ]]
[[ -s /etc/systemd/network/10-cloud-init-eth0.network || -n $(find /etc/systemd/network -name '*.network' -print -quit) ]]
[[ -f /home/matt/.ssh/authorized_keys ]]
touch /etc/cloud/cloud-init.disabled
# xinit must let its session exit before systemd tears down the X server.
mkdir -p /etc/systemd/system/evolution-desktop.service.d
cat > /etc/systemd/system/evolution-desktop.service.d/stop.conf <<'UNIT'
[Service]
ExecStop=-/usr/bin/runuser -u matt -- /usr/bin/env XDG_RUNTIME_DIR=/run/user/1000 /usr/bin/systemctl --user stop terminal-fast-desktop.service bmos-daily-desktop.service
ExecStop=-/usr/bin/pkill -TERM -u 1000 -x picom
ExecStop=-/usr/bin/runuser -u matt -- /usr/bin/env DISPLAY=:0 XAUTHORITY=/home/matt/.Xauthority /usr/bin/bspc quit
TimeoutStopSec=10
UNIT
systemctl daemon-reload
