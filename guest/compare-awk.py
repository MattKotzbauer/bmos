"""Compare complete decoder-input bytes before selecting an AWK runtime setting."""
import hashlib,json,os,pathlib,subprocess,time
assert pathlib.Path('/etc/os-evolution-guest').read_text().strip()=='arch-baseline'
root=pathlib.Path('/home/matt/bmos-build/linux/src');records=[]
for mode in ['default','GNU-matchers']:
 env=dict(os.environ);env.pop('GAWK_GNU_MATCHERS',None)
 if mode=='GNU-matchers':env['GAWK_GNU_MATCHERS']='1'
 start=time.perf_counter()
 dump=subprocess.Popen(['objdump','-d','-j','.text',str(root/'vmlinux')],stdout=subprocess.PIPE)
 awk=subprocess.Popen(['awk','-f',str(root/'arch/x86/tools/objdump_reformat.awk')],stdin=dump.stdout,stdout=subprocess.PIPE,env=env)
 dump.stdout.close();digest=hashlib.sha256();size=lines=0
 while data:=awk.stdout.read(1024*1024):digest.update(data);size+=len(data);lines+=data.count(b'\n')
 assert awk.wait()==0 and dump.wait()==0
 record=dict(mode=mode,seconds=time.perf_counter()-start,sha256=digest.hexdigest(),bytes=size,lines=lines);records.append(record);print(json.dumps(record),flush=True)
assert records[0]['sha256']==records[1]['sha256'] and records[0]['bytes']==records[1]['bytes']
(root.parent/'awk-full-comparison.json').write_text(json.dumps(dict(entireDisassemblyIdentical=True,results=records),indent=2))
