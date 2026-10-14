"""Fail closed on unexpected published paths and common credential formats.

Only prints filenames/rule names, never matching credential text. This is an
additional guard; publish only reviewed source, never a private lab's history.
"""
import pathlib, re, subprocess, sys
root=pathlib.Path(__file__).resolve().parents[1]
allowed=re.compile(r'(README\.md|\.gitignore|bmos\.ts|(?:tools|guest|evaluator)/[\w.-]+\.(?:py|sh)|recipes/[\w.-]+\.json|docs/[\w.-]+\.md)\Z')
rules={
 'private-key':rb'-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----',
 'openai-key':rb'sk-(?:proj-|svcacct-|ant-)?[A-Za-z0-9_-]{24,}',
 'github-token':rb'(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})',
 'aws-key':rb'(?:AKIA|ASIA)[A-Z0-9]{16}',
 'jwt':rb'eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}',
 'slack-token':rb'xox[baprs]-[A-Za-z0-9-]{20,}',
}
paths=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode().split('\0')
failed=[]
for name in filter(None,paths):
 p=root/name
 if not allowed.fullmatch(name) or p.is_symlink():failed.append((name,'unapproved-path'));continue
 data=p.read_bytes()
 if len(data)>200_000:failed.append((name,'unexpected-size'))
 for label,pattern in rules.items():
  if re.search(pattern,data):failed.append((name,label))
 if name=='README.md' and data:failed.append((name,'README-must-be-blank'))
# Optional private local values are compared in memory, never written to reports.
if len(sys.argv)>1:
 secrets=pathlib.Path(sys.argv[1]).read_bytes()
 values=[]
 for line in secrets.splitlines():
  match=re.match(rb'(?:export\s+)?[A-Z][A-Z0-9_]*\s*=\s*[\"\']?([^\r\n]+)',line)
  if match:
   value=match[1].strip().strip(b'\"\'')
   if len(value)>=12 and b'$' not in value:values.append(value)
 for name in filter(None,paths):
  data=(root/name).read_bytes()
  if any(v in data for v in values):failed.append((name,'known-local-secret'))
for name,rule in failed:print(f'{name}: {rule}')
print(f'Reviewed {len(list(filter(None,paths)))} tracked paths; credential findings: {len(failed)}')
raise SystemExit(bool(failed))
