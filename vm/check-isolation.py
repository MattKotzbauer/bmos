"""Check the actual live terminal VM, including the narrowly shared render node."""
import json,os
from pathlib import Path

root = Path(os.environ['BMOS_LAB'])
processes = []
for p in Path('/proc').iterdir():
    try:
        if p.name.isdigit() and (p/'comm').read_text().strip() == 'qemu-system-x86':
            args = (p/'cmdline').read_bytes().split(b'\0')
            assert b'os-evolution-terminal' in args, 'Another VM is running'
            processes.append((p,args))
    except FileNotFoundError:
        pass
assert len(processes) == 1
p,args = processes[0]
assert b'virtio-keyboard-pci,id=terminal-keyboard' in args
gpu = any(arg.split(b',',1)[0] == b'virtio-vga-gl' for arg in args)
status = dict(line.split(':',1) for line in (p/'status').read_text().splitlines())
assert status['Uid'].split() == ['1000']*4 and int(status['CapEff'],16) == 0
assert status['NoNewPrivs'].strip() == '1' and status['Seccomp'].strip() == '2'
namespaces = {}
for name in ['mnt','pid','net','user','ipc','uts']:
    namespaces[name] = str((p/'ns'/name).readlink())
    assert namespaces[name] != str((Path('/proc/self/ns')/name).readlink())
assert not (p/'root/home/matt/.secrets').exists()
assert not (p/'root/home/matt/.ssh').exists()
assert not (p/'root'/str(root/'private').lstrip('/')).exists()
mounts = (p/'mountinfo').read_text().splitlines()
devices = {line.split()[4] for line in mounts if line.split(' - ',1)[1].split()[0]=='devtmpfs'}
expected = {'/dev/'+name for name in ['null','zero','full','random','urandom','tty','kvm']}
if gpu: expected.add('/dev/dri/renderD128')
assert devices == expected, devices
parents = [root/'artifacts/arch-baseline.qcow2',root/'artifacts/arch-images/Arch-Linux-x86_64-cloudimg-20261001.604814.qcow2']
for dest in ['/usr','/seed.iso', *map(str,parents), *(['/sys'] if gpu else [])]:
    assert any(line.split()[4]==dest and 'ro' in line.split()[5].split(',') for line in mounts),dest
writable = [line.split()[4] for line in mounts if 'rw' in line.split()[5].split(',')
            and line.split(' - ',1)[1].split()[0] not in ['tmpfs','proc','devpts','devtmpfs']]
assert sorted(writable)==sorted([str(root/'artifacts/terminal-fast.qcow2'),'/work'])
assert [line.split(':')[0].strip() for line in (p/'net/dev').read_text().splitlines()[2:]]==['lo']
assert args[args.index(b'-netdev')+1]==b'user,id=n0,restrict=on,ipv6=off,hostfwd=tcp:127.0.0.1:22240-:22'
assert args[args.index(b'-m')+1]==b'2048' and args[args.index(b'-smp')+1]==b'2'
cgroup = Path('/sys/fs/cgroup')/(p/'cgroup').read_text().strip().split('::')[1].lstrip('/')
assert cgroup.name=='os-evolution-terminal.service'
limits = {name:(cgroup/name).read_text().strip() for name in ['memory.max','memory.swap.max','cpu.max','pids.max']}
assert limits=={'memory.max':'3221225472','memory.swap.max':'0','cpu.max':'200000 100000','pids.max':'128'}
gpu_fds = {}
for fd in (p/'fd').iterdir():
    try:
        if str(fd.readlink()).startswith('/dev/dri/'):
            assert str(fd.readlink())=='/dev/dri/renderD128'
            gpu_fds[fd.name]=(p/'fdinfo'/fd.name).read_text()
    except FileNotFoundError:
        pass
if gpu: assert gpu_fds, 'GPU selected but no render node opened'
print(json.dumps(dict(pid=int(p.name),gpu=gpu,gpuFDs=gpu_fds,limits=limits,
                     namespaces=namespaces,devices=sorted(devices),mounts=mounts),indent=2))
