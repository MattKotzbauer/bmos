"""Prove real compile errors, skipped deployment and stale processes fail closed.
Run only in the idle private test VM. Restores the managed host source on exit;
run the normal tmux recipe afterward to rebuild/redeploy the restored source.
"""
import fcntl,json,os,pathlib,subprocess,time
root=pathlib.Path(os.environ['BMOS_LAB']);here=pathlib.Path(__file__).resolve().parents[1]
guard=(root/'runtime/bmos-pipeline.lock').open('a')
try:fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Another build/verification run is active')
env={**os.environ,'BMOS_LOCKED':'1'};env.pop('BMOS_STARTED_NS',None)
source=root/'artifacts/bmos-sources/tmux-3.7c/tmux.c';original=source.read_bytes()
assert original.count(b'TMUX_VERSION "-bmos.1"')==1
out=root/'artifacts/bmos-negative-results'/str(time.time_ns());out.mkdir(parents=True,mode=0o700)
recipe=json.loads((here/'recipes/tmux.json').read_text());records=[]
def guest(command):return subprocess.check_output(['bash',str(here/'vm/guest.sh'),command],text=True).strip()
def attempt(name,expected_stage,changes):
 candidate={**recipe,**changes};path=out/(name+'.json');path.write_text(json.dumps(candidate))
 result=subprocess.run(['bun',str(here/'bmos.ts'),str(path)],capture_output=True,text=True,env=env)
 (out/(name+'.log')).write_text(result.stdout+result.stderr)
 reports=[pathlib.Path(line)/'result.json' for line in result.stdout.splitlines() if line.startswith(str(root/'artifacts/bmos-results/'))]
 assert len(reports)==1,result.stdout+result.stderr
 report=json.loads(reports[0].read_text());assert result.returncode==1 and not report['functionalPass']
 assert report['stages'][-1]['name']==expected_stage and not report['stages'][-1]['passed'],report
 records.append(dict(control=name,rejected=True,stage=expected_stage,evidence=str(reports[0])))
try:
 before=guest('sha256sum /usr/local/bin/tmux')
 source.write_bytes(original+b'\n#error BMOS_INTENTIONAL_COMPILE_FAILURE\n')
 attempt('compile-error','build',{})
 assert guest('sha256sum /usr/local/bin/tmux')==before
 source.write_bytes(original.replace(b'TMUX_VERSION "-bmos.1"',b'TMUX_VERSION "-bmos.negative"'))
 attempt('skipped-deployment','verify-live-artifact',dict(deploy='true',restart='none'))
 assert guest('sha256sum /usr/local/bin/tmux')==before
 attempt('stale-running-process','verify-live-artifact',dict(restart='none'))
 assert guest('sha256sum /usr/local/bin/tmux')!=before
finally:
 source.write_bytes(original)
 (out/'result.json').write_text(json.dumps(dict(sourceRestored=source.read_bytes()==original,controls=records),indent=2))
print(out)
