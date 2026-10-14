"""Save/restore the daily editor through real tmux keys across an external reboot.
Use `save`, then cleanly reboot/build, launch daily, then `restore`.
"""
import fcntl,hashlib,json,os,pathlib,shlex,subprocess,sys,time
root=pathlib.Path(os.environ['BMOS_LAB']);here=pathlib.Path(__file__).resolve().parents[1]
guard=(root/'runtime/bmos-pipeline.lock').open('a');fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
sys.path.insert(0,str(here/'evaluator'))
from qmp import QMP
from framebuffer import Framebuffer
out=root/'private/bmos-daily-persistence';out.mkdir(mode=0o700,exist_ok=True)
guest=lambda s:subprocess.check_output(['bash',str(here/'vm/guest.sh'),s],text=True).strip()
pane=lambda:guest('tmux -L bmos-daily capture-pane -p')
q=QMP();fb=Framebuffer()
def wait(predicate,seconds=12):
 deadline=time.monotonic()+seconds
 while time.monotonic()<deadline:
  frame=fb.capture()
  if predicate():return frame
  time.sleep(.03)
 raise AssertionError('Expected daily workflow state did not arrive')
try:
 if sys.argv[1]=='save':
  report=json.loads(pathlib.Path(sys.argv[2]).read_text());scratch=report['scratch']
  assert guest("tmux -L bmos-daily display-message -p '#{pane_current_command}'")=='bash'
  q.text('nvim '+shlex.quote(scratch)+'\n');wait(lambda:'BMOS_DAILY_EDIT_OK' in pane())
  q.key('alt+q');wait(lambda:len(guest('tmux -L bmos-daily list-panes').splitlines())==2)
  q.key('alt+h');wait(lambda:'BMOS_DAILY_EDIT_OK' in pane())
  q.key('ctrl+b');q.key('ctrl+s')
  wait(lambda:guest('test -f ~/.local/share/bmos/daily-resurrect/last && echo saved || true')=='saved')
  saved=guest('cat ~/.local/share/bmos/daily-resurrect/last');assert 'nvim -S' in saved
  state=dict(scratch=scratch,sha256=report['scratchSha256'],boot=guest('cat /proc/sys/kernel/random/boot_id'),sessionSha256=hashlib.sha256(saved.encode()).hexdigest())
  (out/'before.json').write_text(json.dumps(state,indent=2));fb.capture().save(out/'saved.png')
  # Close only the test-created, saved editor and its two shells via real keys.
  q.key('escape');q.text(':q\n');wait(lambda:guest("tmux -L bmos-daily display-message -p '#{pane_current_command}'")=='bash')
  q.text('exit\n');wait(lambda:len(guest('tmux -L bmos-daily list-panes').splitlines())==1)
  q.text('exit\n')
  wait(lambda:guest('tmux -L bmos-daily has-session 2>/dev/null && echo active || true')=='')
  print('Daily editor/session saved; test-created shells closed.')
 elif sys.argv[1]=='restore':
  state=json.loads((out/'before.json').read_text());assert guest('cat /proc/sys/kernel/random/boot_id')!=state['boot']
  assert guest('sha256sum '+shlex.quote(state['scratch'])).split()[0]==state['sha256']
  saved=guest('cat ~/.local/share/bmos/daily-resurrect/last');assert hashlib.sha256(saved.encode()).hexdigest()==state['sessionSha256']
  start=time.perf_counter();q.key('ctrl+b');q.key('ctrl+r')
  acknowledged=False
  def restored():
   global acknowledged
   text=pane()
   if 'Press ENTER or type command to continue' in text and not acknowledged:
    q.key('enter');acknowledged=True;return False
   return len(guest('tmux -L bmos-daily list-panes').splitlines())==2 and 'BMOS_DAILY_EDIT_OK' in text
  wait(restored,20)
  until=time.monotonic()+.3
  while time.monotonic()<until:frame=fb.capture()
  frame.save(out/'restored.png');(out/'after.json').write_text(json.dumps(dict(nativePass=True,fileInfoPromptAcknowledged=acknowledged,restoreSeconds=time.perf_counter()-start,manualPixelReviewRequired=True),indent=2));print('Saved note and two-pane daily session restored after a different boot.')
 else:raise SystemExit('Expected save or restore')
finally:q.close();fb.close()
