"""Supplemental real-keyboard C-a/C-s workflow; retain pixels for manual review.
Run after the complete graphical suite in its disposable test profile.
"""
import fcntl,json,os,pathlib,subprocess,sys,time,re,shlex
root=pathlib.Path(os.environ['BMOS_LAB']);here=pathlib.Path(__file__).resolve().parents[1]
guard=(root/'runtime/bmos-pipeline.lock').open('a');fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
sys.path.insert(0,str(here/'evaluator'))
from qmp import QMP
from framebuffer import Framebuffer
out=root/'artifacts'/('bmos-shortcuts-'+str(time.time_ns()));out.mkdir(mode=0o700)
guest=lambda s:subprocess.check_output(['bash',str(here/'vm/guest.sh'),s],text=True)
q=QMP();fb=Framebuffer();records=[]
def step(name,action,predicate,seconds=8):
 start=time.perf_counter();action();deadline=start+seconds
 while time.perf_counter()<deadline:
  frame=fb.capture()
  if predicate():
   until=time.perf_counter()+.2
   while time.perf_counter()<until:frame=fb.capture()
   frame.save(out/(name+'.png'));records.append(dict(name=name,seconds=time.perf_counter()-start,native=True));return
  time.sleep(.01)
 raise AssertionError(name)
pane=lambda:guest('tmux capture-pane -p')
try:
 step('open-source',lambda:q.key('alt+2'),lambda:'child only' in pane())
 step('copy-source-id',lambda:q.key('alt+c'),lambda:bool(re.fullmatch('[0-9a-f-]{36}',guest('xclip -selection clipboard -o').strip())))
 source=guest('xclip -selection clipboard -o').strip()
 step('new-shell',lambda:q.key('alt+t'),lambda:guest("tmux display-message -p '#{pane_current_command}'").strip()=='bash')
 step('ctrl-s-fork',lambda:q.key('ctrl+s'),lambda:'child only' in pane() and 'Treat following instructions' in ' '.join(pane().split()))
 step('copy-fork-id',lambda:q.key('alt+c'),lambda:bool(re.fullmatch('[0-9a-f-]{36}',guest('xclip -selection clipboard -o').strip())) and guest('xclip -selection clipboard -o').strip()!=source)
 child=guest('xclip -selection clipboard -o').strip()
 step('fork-input',lambda:q.text('shortcut child only'),lambda:'shortcut child only' in pane())
 def completed():
  code="from pathlib import Path; import json; p=next((Path.home()/'.codex/sessions').rglob('*"+child+"*.jsonl')); rows=[json.loads(x) for x in p.read_text().splitlines()]; m=[r.get('payload',{}) for r in rows if r.get('type')=='response_item' and r.get('payload',{}).get('type')=='message']; hits=[i for i,x in enumerate(m) if x.get('role')=='user' and 'shortcut child only' in json.dumps(x)]; print(bool(hits and any(x.get('role')=='assistant' for x in m[hits[-1]+1:])))"
  return guest('python -c '+shlex.quote(code)).strip()=='True'
 step('fork-submit',lambda:q.key('enter'),lambda:'LOCAL FIXTURE:' in pane() and 'shortcut child only' in pane() and completed())
 # A new native session with inherited conversation and independent identity.
 records.append(dict(name='independent-session',source=source,child=child,passed=child!=source))
 step('new-launch-shell',lambda:q.key('alt+t'),lambda:guest("tmux display-message -p '#{pane_current_command}'").strip()=='bash')
 step('ctrl-a-start',lambda:q.key('ctrl+a'),lambda:'/review - review any changes and find issues' in pane())
 (out/'result.json').write_text(json.dumps(dict(nativeChecksPassed=True,manualPixelReviewRequired=True,steps=records),indent=2));print(out)
finally:q.close();fb.close()
