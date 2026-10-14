#!/usr/bin/env bash
set -euo pipefail
socat UNIX-LISTEN:/work/ssh.sock,fork,unlink-early,mode=0600 TCP:127.0.0.1:22240 &
graphics=(-display none -vga virtio -vnc unix:/work/vnc.sock)
if [[ $2 == gpu ]]; then
  graphics=(-display egl-headless,rendernode=/dev/dri/renderD128 -vga none -device virtio-vga-gl,id=video0 -vnc unix:/work/vnc.sock)
fi
exec /usr/bin/qemu-system-x86_64 -no-user-config -nodefaults \
  -name os-evolution-terminal -machine q35,accel=kvm -cpu host -smp 2 -m 2048 \
  -device virtio-keyboard-pci,id=terminal-keyboard \
  -smbios type=11,value=io.systemd.credential:systemd.extra-unit.systemd-networkd-wait-online.service= \
  -smbios type=11,value=io.systemd.credential:systemd.extra-unit.systemd-time-wait-sync.service= \
  -sandbox on,obsolete=deny,elevateprivileges=deny,spawn=deny,resourcecontrol=deny \
  -drive "file=$1,format=qcow2,if=virtio,cache=none" \
  -drive file=/seed.iso,format=raw,media=cdrom,readonly=on \
  -netdev user,id=n0,restrict=on,ipv6=off,hostfwd=tcp:127.0.0.1:22240-:22 \
  -device virtio-net-pci,netdev=n0 "${graphics[@]}" -monitor none \
  -qmp unix:/work/qmp.sock,server=on,wait=off \
  -chardev ringbuf,id=serial,size=1048576 -serial chardev:serial
