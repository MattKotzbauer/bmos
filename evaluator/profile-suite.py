"""Bounded CPU/kernel-time and GPU-engine counter samples for the same workflow.
Counter profiles, not instruction-level stacks or physical key-to-photon data.
"""
import json, os, subprocess, time, threading
from pathlib import Path
source=Path(__file__).resolve().parent
root=Path(os.environ['BMOS_LAB'])/'candidates/terminal-fast'
qemus=[]
for p in Path('/proc').iterdir():
    try:
        if p.name.isdigit() and (p/'comm').read_text().strip()=='qemu-system-x86':qemus.append(p)
    except FileNotFoundError:pass
assert len(qemus)==1
p=qemus[0];assert b'os-evolution-terminal' in (p/'cmdline').read_bytes()
cgroup=Path('/sys/fs/cgroup')/(p/'cgroup').read_text().strip().split('::')[1].lstrip('/')
fd=next(f for f in (p/'fdinfo').iterdir() if 'drm-driver:' in f.read_text())
start=time.perf_counter();samples=[];stop=threading.Event()
def sample():
    cpu={k:int(v) for k,v in (line.split() for line in (cgroup/'cpu.stat').read_text().splitlines())}
    gpu={}
    for line in fd.read_text().splitlines():
        if line.startswith('drm-engine-') or line.startswith('drm-memory-'):
            k,v=line.split(':',1);gpu[k]=v.strip()
    stat=(p/'stat').read_text().split(') ',1)[1].split()
    samples.append(dict(seconds=time.perf_counter()-start,cgroupCPU=cpu,qemuUserTicks=int(stat[11]),qemuKernelTicks=int(stat[12]),gpu=gpu))
def monitor():
    while not stop.wait(.05):sample()
sample();worker=threading.Thread(target=monitor);worker.start()
try:
    run=subprocess.run(['python',str(source/'visual-suite.py')],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
finally:stop.set();worker.join();sample()
wall=time.perf_counter()-start
out=root/'evidence'/('profile-'+str(time.time_ns())+'.json')
out.write_text(json.dumps(dict(wallSeconds=wall,budgetMet=wall<=20,passed=run.returncode==0 and wall<=20,exitCode=run.returncode,cpuLimit=(cgroup/'cpu.max').read_text().strip(),clockTicks=os.sysconf('SC_CLK_TCK'),stdout=run.stdout,samplePeriodSeconds=.05,samples=samples),indent=2))
print(run.stdout);print(out);print('INVOCATION_WALL',wall)
raise SystemExit(run.returncode if run.returncode else (0 if wall<=20 else 1))
