"""Prove that the newly linked kernel is running, rather than merely installed."""
import pathlib,json,hashlib,platform
root=pathlib.Path('/home/matt/bmos-build/linux');expected=json.loads((root/'expected-kernel.json').read_text())
assert platform.release()==expected['release']
assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=expected['previousBootId']
assert hashlib.sha256(pathlib.Path('/sys/kernel/notes').read_bytes()).hexdigest()==expected['notesSha256']
assert hashlib.sha256(pathlib.Path('/boot/vmlinuz-bmos').read_bytes()).hexdigest()==expected['imageSha256']
print(json.dumps(dict(runningKernelVerified=True,**expected)))
