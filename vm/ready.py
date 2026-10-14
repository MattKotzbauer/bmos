"""Wait for the real guest desktop; report cold-start readiness separately."""
import subprocess,time,json,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evaluator'))
from framebuffer import Framebuffer
start=time.perf_counter();root=Path(__file__).resolve().parent
while time.perf_counter()-start<60:
    result=subprocess.run(['bash',str(root/'guest.sh'),'tmux list-clients -F "#{client_session}"; tmux capture-pane -p'],capture_output=True,text=True,timeout=12)
    if result.returncode==0 and result.stdout.startswith('terminal\n') and '[matt@evolution-baseline workspace]$' in result.stdout:
        fb=Framebuffer();image=fb.capture();fb.close()
        image.save(Path(os.environ['BMOS_LAB'])/'candidates/terminal-fast/evidence/boot-desktop.ppm')
        record=dict(desktopReadySeconds=time.perf_counter()-start,displaySize=image.size,tmux=result.stdout)
        (Path(os.environ['BMOS_LAB'])/'candidates/terminal-fast/evidence/boot-ready.json').write_text(json.dumps(record,indent=2));print(json.dumps(record));break
    time.sleep(.2)
else:raise SystemExit('Guest desktop did not become ready within60s')
