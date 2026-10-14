#!/usr/bin/env bash
set -euo pipefail
source_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
cd "${BMOS_LAB:?Set BMOS_LAB to the private lab}"
root=$PWD
disk=$root/artifacts/terminal-fast.qcow2
parent=$root/artifacts/arch-baseline.qcow2
base=$root/artifacts/arch-images/Arch-Linux-x86_64-cloudimg-20261001.604814.qcow2
work=$root/runtime/terminal-fast
# Reserve all remaining possible guest-disk growth plus 1 GiB overhead.
allocated=0
if [[ -e "$disk" ]]; then allocated=$(du -B1 "$disk" | cut -f1); fi
# Reserve the full bounded possible file growth, including retained snapshots.
required=$((100*1024*1024*1024 + 14*1024*1024*1024 - allocated + 1024*1024*1024))
[[ $(df --output=avail -B1 . | tail -1) -ge $required ]]
[[ $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) -ge 4194304 ]]
[[ ${INVOCATION_ID:-} && $(cat /proc/self/cgroup) == *os-evolution-terminal.service* ]]
exec 9>runtime/vm.lock
flock -n -E 73 9
[[ -f "$parent" && ! -L "$parent" && $(stat -c %a "$parent") == 444 ]]
if [[ ! -e "$disk" ]]; then qemu-img create -f qcow2 -F qcow2 -b "$parent" "$disk"; fi
[[ -f "$disk" && ! -L "$disk" && -w "$disk" && $(stat -c %a "$disk") != 444 ]]
devices=()
if [[ $1 == gpu ]]; then
  [[ -r /dev/dri/renderD128 && -w /dev/dri/renderD128 ]]
  [[ $(readlink -f /sys/class/drm/renderD128/device/driver) == /sys/bus/pci/drivers/i915 ]]
  devices=(--dev-bind /dev/dri/renderD128 /dev/dri/renderD128 --ro-bind /sys /sys)
else [[ $1 == software ]]; fi
export XDG_CONFIG_HOME=$root/runtime/arch-podman/config
exec podman --root "$root/runtime/arch-podman/store" --runroot "$root/runtime/pod" \
  --storage-driver vfs unshare bwrap \
  --unshare-all --die-with-parent --new-session --cap-drop ALL \
  --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib \
  --symlink usr/lib64 /lib64 --ro-bind /etc/ld.so.cache /etc/ld.so.cache \
  --proc /proc --dev /dev --dev-bind /dev/kvm /dev/kvm --tmpfs /tmp \
  "${devices[@]}" \
  --ro-bind "$base" "$base" --ro-bind "$parent" "$parent" --bind "$disk" "$disk" \
  --ro-bind "$root/runtime/arch-baseline/seed.iso" /seed.iso --bind "$work/io" /work \
  --ro-bind "$source_dir/inside-sandbox.sh" /launch.sh \
  --chdir /work --clearenv --setenv PATH /usr/bin:/bin \
  --setenv __EGL_VENDOR_LIBRARY_FILENAMES /usr/share/glvnd/egl_vendor.d/50_mesa.json \
  /bin/bash /launch.sh "$disk" "$1"
