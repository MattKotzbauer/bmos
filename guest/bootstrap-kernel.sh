#!/usr/bin/env bash
set -euo pipefail
[[ $(cat /etc/os-evolution-guest) == arch-baseline ]]
cd /home/matt/bmos-build/linux/src
[[ -f Makefile && -d arch/x86 ]]
git init -b main
git add .
git -c user.name=BMOS -c user.email=bmos@localhost commit -qm 'Pinned Arch kernel v7.2.9-arch1 source'
zcat /proc/config.gz > .config
make localmodconfig </dev/null
scripts/config --set-str LOCALVERSION -bmos --disable LOCALVERSION_AUTO \
  --disable DEBUG_INFO_DWARF_TOOLCHAIN_DEFAULT --disable DEBUG_INFO_DWARF4 \
  --disable DEBUG_INFO_DWARF5 --enable DEBUG_INFO_NONE --disable DEBUG_INFO_BTF \
  --disable DEBUG_INFO_BTF_MODULES --set-str SYSTEM_TRUSTED_KEYS '' \
  --set-str SYSTEM_REVOCATION_KEYS ''
make olddefconfig
git add -f .config
git -c user.name=BMOS -c user.email=bmos@localhost commit -qm 'Guest hardware configuration with incremental build outputs retained'
printf 'Configured guest kernel: '
make -s kernelrelease
