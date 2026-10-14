"""Exercise a scratch copy of a private note through real virtual keyboard input.

Screenshots stay private and require human pixel review. This supplemental daily
check does not replace the immutable 70-case graphical acceptance contract.
"""
import fcntl,hashlib,json,os,pathlib,shlex,subprocess,sys,time
root=pathlib.Path(os.environ['BMOS_LAB']);here=pathlib.Path(__file__).resolve().parents[1]
guard=(root/'runtime/bmos-pipeline.lock').open('a')
try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Build verification is active')
sys.path.insert(0,str(here/'evaluator'))
from qmp import QMP
from framebuffer import Framebuffer
out=root/'artifacts/bmos-daily-results'/str(time.time_ns());out.mkdir(parents=True,mode=0o700)
guest=lambda command:subprocess.check_output(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/guest.sh'),command])
assert guest("tmux -L bmos-daily display-message -p '#{pane_current_command}'").strip()==b'bash', 'Start from an idle daily shell'
assert len(guest('tmux -L bmos-daily list-panes').splitlines())==1
manifest=json.loads(pathlib.Path(sys.argv[1]).read_text())
# Check every captured note without publishing its name or contents.
for record in manifest['files']:
 data=guest('cat -- '+shlex.quote('/home/matt/thing/'+record['name']))
 assert hashlib.sha256(data).hexdigest()==record['sha256']
source=next(r for r in manifest['files'] if r['name'].endswith('.md'))
original=guest('cat -- '+shlex.quote('/home/matt/thing/'+source['name']))
marker=b'BMOS_DAILY_EDIT_OK\n';scratch='/home/matt/thing/bmos-qualification.txt'
# Never overwrite a user's existing scratch file on rerun.
scratch=scratch.replace('.txt','-'+str(time.time_ns())+'.txt')
q=QMP();fb=Framebuffer();results=[]
def pane():return guest('tmux -L bmos-daily capture-pane -p').decode()
def step(name,action,predicate):
 before=fb.capture();start=time.perf_counter();action();deadline=start+8
 while time.perf_counter()<deadline:
  frame=fb.capture()
  if predicate():
   # Drain subsequent visible paint before retaining evidence for manual review.
   until=time.perf_counter()+.2
   while time.perf_counter()<until:frame=fb.capture()
   frame.save(out/(name+'.png'))
   results.append(dict(name=name,native=True,screenChanged=frame.tobytes()!=before.tobytes(),seconds=time.perf_counter()-start))
   return
  time.sleep(.02)
 raise AssertionError(name+' did not reach its real application outcome')
try:
 step('shell-copy',lambda:q.text('cp -- '+shlex.quote('/home/matt/thing/'+source['name'])+' '+shlex.quote(scratch)+" && printf 'BMOS_COPY_OK\\n'\n"),lambda:'\nBMOS_COPY_OK\n' in pane())
 step('nvim-open-private-copy',lambda:q.text('nvim '+scratch+'\n'),lambda:guest("tmux -L bmos-daily display-message -p '#{pane_current_command}'").strip()==b'nvim' and 'bmos-qualification-' in pane())
 step('edit',lambda:q.text('gg0iBMOS_DAILY_EDIT_OK\njk'),lambda:'BMOS_DAILY_EDIT_OK' in pane())
 step('save',lambda:q.text(' w'),lambda:guest('cat '+shlex.quote(scratch))==marker+original)
 step('close',lambda:(q.key('escape'),q.text(':q\n')),lambda:guest("tmux -L bmos-daily display-message -p '#{pane_current_command}'").strip()==b'bash')
 step('reopen',lambda:q.text('nvim '+scratch+'\n'),lambda:'BMOS_DAILY_EDIT_OK' in pane())
 step('close-again',lambda:(q.key('escape'),q.text(':q\n')),lambda:guest("tmux -L bmos-daily display-message -p '#{pane_current_command}'").strip()==b'bash')
 step('split',lambda:q.key('alt+q'),lambda:len(guest('tmux -L bmos-daily list-panes').splitlines())==2)
 step('split-shell',lambda:q.text("printf 'BMOS_DAILY_PANE_OK\\n'\n"),lambda:'\nBMOS_DAILY_PANE_OK\n' in pane())
 step('close-split',lambda:q.text('exit\n'),lambda:len(guest('tmux -L bmos-daily list-panes').splitlines())==1)
 # Prove the main note was never modified by editing its scratch copy.
 assert guest('cat -- '+shlex.quote('/home/matt/thing/'+source['name']))==original
 record=dict(nativeChecksPassed=True,manualPixelReviewRequired=True,privateCopiesVerified=len(manifest['files']),scratch=scratch,scratchSha256=hashlib.sha256(marker+original).hexdigest(),steps=results)
 (out/'result.json').write_text(json.dumps(record,indent=2));print(out)
finally:q.close();fb.close()
