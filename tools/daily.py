"""Start the private daily desktop, keeping test sessions and note backups separate."""
import fcntl,json,os,pathlib,subprocess,sys,time,hashlib
root=pathlib.Path(os.environ['BMOS_LAB']);here=pathlib.Path(__file__).resolve().parents[1]
guard=(root/'runtime/bmos-pipeline.lock').open('a')
try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('A build/verification run is active; the daily desktop is not switched during it.')
guest=lambda command:subprocess.run(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/guest.sh'),'set -eu; '+command],check=True)
action=sys.argv[1] if len(sys.argv)>1 else 'start'
if action=='start':
 if subprocess.run(['systemctl','--user','is-active','--quiet','os-evolution-terminal']).returncode:
  subprocess.run(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/start.sh'),'gpu'],check=True)
  subprocess.run(['python',str(pathlib.Path(__file__).resolve().parents[1]/'vm/ready.py')],check=True)
 subprocess.run([sys.executable,str(here/'vm/check-isolation.py')],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/guest.sh'),'cat > /home/matt/.local/bin/bmos-daily; chmod 755 /home/matt/.local/bin/bmos-daily'],input=(here/'guest/daily.sh').read_bytes(),check=True)
 guest('systemctl --user stop terminal-fast-desktop.service terminal-model.service; tmux -L default kill-server 2>/dev/null || true; if tmux -L bmos-daily has-session 2>/dev/null; then systemctl --user start bmos-daily-desktop.service; else systemctl --user restart bmos-daily-desktop.service; fi')
 guest("for attempt in {1..100}; do if tmux -L bmos-daily list-clients 2>/dev/null | /usr/bin/grep -q .; then exit 0; fi; sleep .1; done; echo 'Daily terminal did not attach' >&2; exit 1")
 print('Daily desktop started. Notes are private guest copies; test sessions are separate.')
elif action=='backup':
 dest=root/'private/bmos-daily-backups';dest.mkdir(mode=0o700,exist_ok=True);path=dest/(str(time.time_ns())+'.tar')
 # No extraction on the host. Store an opaque archive of guest-owned notes only.
 with path.open('xb') as output:
  subprocess.run(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/guest.sh'),'tar -cf - -C /home/matt thing .local/state/bmos-daily .local/share/bmos/daily-resurrect'],stdout=output,check=True)
 path.chmod(0o600)
 with path.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
 path.with_suffix('.json').write_text(json.dumps(dict(bytes=path.stat().st_size,sha256=digest)))
 print('Private note/session archive:',path)
elif action=='stop':
 # Refuse a silent loss of running editor/application state. The user saves and
 # detaches/closes their sessions explicitly, then this switches back to testing.
 guest('if tmux -L bmos-daily has-session 2>/dev/null; then echo "Save your files/session and close the daily tmux session first." >&2; exit 70; fi; systemctl --user stop bmos-daily-desktop.service; systemctl --user start terminal-model.service terminal-fast-desktop.service')
else:raise SystemExit('Expected start, backup, or stop')
