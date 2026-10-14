"""Transfer changed tracked source bytes; retain incremental guest build outputs."""
import hashlib,json,os,pathlib,subprocess,sys,tarfile
root=pathlib.Path(os.environ['BMOS_LAB']);source=pathlib.Path(sys.argv[1]).resolve();name=sys.argv[2]
assert name.replace('-','').isalnum() and source.is_dir()
guard=['bash',str(root/'candidates/terminal-fast/guest.sh')]
files=subprocess.check_output(['git','-C',str(source),'ls-files','-z']).decode().split('\0');manifest={}
for f in filter(None,files):
 p=source/f
 if not p.exists():continue
 assert not p.is_symlink() and p.is_relative_to(source),f
 assert not any(part in ['.env','.secrets','auth.json','credentials.json'] for part in p.relative_to(source).parts),f
 manifest[f]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),mode=p.stat().st_mode&0o777)
assert manifest,'Track source files in Git before testing'
dest=f'/home/matt/bmos-build/{name}'
old=subprocess.check_output(guard+[f"cat {dest}/source-manifest.json 2>/dev/null || printf '{{}}'"],text=True);previous=json.loads(old)
changed=[f for f,v in manifest.items() if previous.get(f)!=v]
changed=[f for f,v in manifest.items() if previous.get(f)!=v]
process=subprocess.Popen(guard+[f'mkdir -p {dest}/src; tar -xf - -C {dest}/src'],stdin=subprocess.PIPE)
with tarfile.open(fileobj=process.stdin,mode='w|') as tar:
 for f in changed:tar.add(source/f,arcname=f,recursive=False)
process.stdin.close();assert process.wait()==0
metadata=dict(files=manifest,deleted=sorted(set(previous)-set(manifest)))
# All deletions are relative paths previously recorded by this managed sync.
script="""import pathlib,json,sys,hashlib
root=pathlib.Path(sys.argv[1]); m=json.load(sys.stdin)
for f in m['deleted']:
 p=(root/'src'/f).resolve();assert p.is_relative_to(root/'src');p.unlink(missing_ok=True)
for f,v in m['files'].items():
 p=root/'src'/f;assert hashlib.sha256(p.read_bytes()).hexdigest()==v['sha256'],f
(root/'source-manifest.json').write_text(json.dumps(m['files'],sort_keys=True))
"""
import shlex
subprocess.run(guard+[f'python -c {shlex.quote(script)} {dest}'],input=json.dumps(metadata).encode(),check=True)
print(hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest())
