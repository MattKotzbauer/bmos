"""Install a compiled kernel inside the disposable guest, preserving the stock boot entry."""
import hashlib,json,os,pathlib,re,shlex,subprocess
assert pathlib.Path('/etc/os-evolution-guest').read_text().strip()=='arch-baseline'
assert os.geteuid()==0
source=pathlib.Path('/home/matt/bmos-build/linux/src');os.chdir(source)
run=lambda args:subprocess.check_output(args,text=True).strip()
release=run(['make','-s','kernelrelease']);assert re.fullmatch(r'[\w.+-]+-bmos',release),release
subprocess.run(['make','-j2','modules_install','INSTALL_MOD_STRIP=1'],check=True)
subprocess.run(['install','-m644','arch/x86/boot/bzImage','/boot/vmlinuz-bmos'],check=True)
subprocess.run(['mkinitcpio','-k',release,'-g','/boot/initramfs-bmos.img'],check=True)
subprocess.run(['objcopy','--dump-section','.notes=../kernel.notes','vmlinux'],check=True)
notes=(source.parent/'kernel.notes').read_bytes()
params=pathlib.Path('/proc/cmdline').read_text().split();params=[p for p in params if not p.startswith('BOOT_IMAGE=')]
uuid=run(['findmnt','-no','UUID','/']);assert re.fullmatch(r'[0-9a-f-]+',uuid)
entry=f"""menuentry 'BMOS compiled kernel' --id bmos {{
    insmod btrfs
    search --no-floppy --fs-uuid --set=root {uuid}
    linux /boot/vmlinuz-bmos {' '.join(shlex.quote(p) for p in params)}
    initrd /boot/initramfs-bmos.img
}}
"""
p=pathlib.Path('/etc/grub.d/09_bmos');p.write_text("#!/bin/sh\ncat <<'BMOS_ENTRY'\n"+entry+'BMOS_ENTRY\n');p.chmod(0o755)
subprocess.run(['grub-mkconfig','-o','/boot/grub/grub.cfg'],check=True)
record=dict(release=release,notesSha256=hashlib.sha256(notes).hexdigest(),imageSha256=hashlib.sha256(pathlib.Path('/boot/vmlinuz-bmos').read_bytes()).hexdigest(),previousBootId=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip())
(source.parent/'expected-kernel.json').write_text(json.dumps(record,indent=2))
print(json.dumps(record))
