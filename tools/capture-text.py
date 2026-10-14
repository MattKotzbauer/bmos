"""Privately snapshot editable project files, excluding credentials and generated data.
Never modifies the source tree or writes personal data inside the public repo.
"""
import hashlib,io,json,os,pathlib,re,stat,tarfile,time
root=pathlib.Path(os.environ['BMOS_LAB']).resolve();source=pathlib.Path.home()/'thing'
out=root/'private'/('bmos-text-'+str(time.time_ns()));out.mkdir(mode=0o700)
skip={'.git','node_modules','.venv','venv','__pycache__','target','dist','build','.next','.cache','.svelte-kit','artifacts','logs','log','results','runs','checkpoints','datasets','vendor','third_party','.codex','.claude','.ssh','.aws','.gnupg','site-packages'}
sensitive=re.compile(r'(^\.env(?:\.|$)|^\.secrets|auth\.json|credentials|password|pwds|token|id_rsa|id_ed25519|\.pem$|\.key$)',re.I)
patterns=[rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',rb'sk-(?:proj-|svcacct-|ant-)?[A-Za-z0-9_-]{24,}',rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',rb'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',rb'(?:AKIA|ASIA)[A-Z0-9]{16}']
known=[]
secret=pathlib.Path.home()/'.secrets'
if secret.exists():
 for line in secret.read_bytes().splitlines():
  m=re.match(rb'(?:export\s+)?[A-Z][A-Z0-9_]*\s*=\s*[\"\']?([^\r\n]+)',line)
  if m:
   value=m[1].strip().strip(b'\"\'')
   if len(value)>=12 and b'$' not in value:known.append(value)
records=[];excluded=[];total=0
archive=out/'textfiles.tar'
with archive.open('xb') as output,tarfile.open(fileobj=output,mode='w') as tar:
 for base,dirs,files in os.walk(source,followlinks=False):
  kept=[]
  for name in dirs:
   p=pathlib.Path(base,name)
   if p.resolve()==root or p.is_symlink() or name in skip or any(x in name.lower() for x in ('snapshot-','-backups','-backup','-bundles','-worktrees')) or name.startswith('zig-x86_64-'):
    excluded.append(dict(name=str(p.relative_to(source)),reason='generated-or-private-directory'));continue
   kept.append(name)
  dirs[:]=kept
  for name in files:
   p=pathlib.Path(base,name);relative=str(p.relative_to(source));reason=None
   try:
    info=p.lstat()
    if not stat.S_ISREG(info.st_mode):reason='not-regular'
    elif sensitive.search(name):reason='credential-name'
    elif info.st_size>2*1024**2:reason='large-file'
    elif p.suffix.lower() in {'.log','.jsonl','.normalized','.stdout','.stderr','.csv','.tsv','.time','.db-wal','.db-shm'}:reason='generated-data'
    if reason:excluded.append(dict(name=relative,reason=reason));continue
    data=p.read_bytes()
    if b'\0' in data:continue
    data.decode('utf-8')
    if any(re.search(pattern,data) for pattern in patterns) or any(v in data for v in known):
     excluded.append(dict(name=relative,reason='credential-content'));continue
    if total+len(data)>750*1024**2:raise RuntimeError('Private text copy exceeds 750 MiB; inspect exclusions before continuing')
    member=tarfile.TarInfo(relative);member.size=len(data);member.mode=0o700 if info.st_mode&0o111 else 0o600;member.mtime=int(info.st_mtime)
    tar.addfile(member,io.BytesIO(data));total+=len(data)
    records.append(dict(name=relative,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),mode=oct(member.mode)))
   except (UnicodeError,OSError):continue
archive.chmod(0o400)
manifest=out/'manifest.json';manifest.write_text(json.dumps(dict(capturedAt=time.time(),source=str(source),files=records,excluded=excluded),indent=2));manifest.chmod(0o400)
print(json.dumps(dict(privateSnapshot=str(out),files=len(records),bytes=total,excluded=len(excluded))))
