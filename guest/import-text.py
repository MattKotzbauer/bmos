"""Import an owner-approved regular-file snapshot without replacing guest edits."""
import hashlib,json,pathlib,tarfile,sys,os
assert pathlib.Path('/etc/os-evolution-guest').read_text().strip()=='arch-baseline'
root=pathlib.Path.home()/'thing';root.mkdir(mode=0o700,exist_ok=True)
manifest=json.loads(pathlib.Path(sys.argv[1]).read_text());expected={r['name']:r for r in manifest['files']};imported=[];conflicts=[]
with tarfile.open(fileobj=sys.stdin.buffer,mode='r|') as archive:
 for member in archive:
  relative=pathlib.PurePosixPath(member.name)
  assert member.isfile() and not relative.is_absolute() and '..' not in relative.parts
  target=root/relative;assert member.name in expected
  if any(p.is_symlink() for p in [target,*target.parents]):
   conflicts.append(member.name);continue
  data=archive.extractfile(member).read();record=expected[member.name]
  assert hashlib.sha256(data).hexdigest()==record['sha256']
  if target.exists():
   if hashlib.sha256(target.read_bytes()).hexdigest()!=record['sha256']:
    conflicts.append(member.name);continue
  else:
   target.parent.mkdir(mode=0o700,parents=True,exist_ok=True)
   with target.open('xb') as output:output.write(data)
   target.chmod(member.mode&0o700)
  assert hashlib.sha256(target.read_bytes()).hexdigest()==record['sha256']
  imported.append(member.name)
assert len(imported)+len(conflicts)==len(expected)
out=pathlib.Path(sys.argv[1]).with_name('import-result.json');out.write_text(json.dumps(dict(verified=len(imported),conflicts=conflicts),indent=2))
print(json.dumps(dict(verified=len(imported),preservedConflicts=len(conflicts))))
