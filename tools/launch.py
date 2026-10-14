"""Start the private daily VM and bounded loopback services; print its private URL."""
import os,pathlib,shutil,subprocess,sys
root=pathlib.Path(os.environ['BMOS_LAB']).resolve();here=pathlib.Path(__file__).resolve().parent
run=lambda args:subprocess.run(args,check=True)
run([sys.executable,str(here/'daily.py'),'start'])
def service(name,memory,tasks,command):
 if subprocess.run(['systemctl','--user','is-active','--quiet',name]).returncode==0:return
 run(['systemd-run','--user','--unit='+name,'--collect','-p','MemoryMax='+memory,'-p','MemorySwapMax=0','-p','CPUQuota=25%','-p','TasksMax='+str(tasks),'-p','Restart=on-failure','-p','RestartSec=3','--setenv=BMOS_LAB='+str(root),*command])
service('bmos-viewer','256M',32,[shutil.which('bun'),str(here/'desktop.ts')])
service('bmos-egress','128M',32,[sys.executable,str(here/'egress.py')])
service('bmos-egress-tunnel','96M',16,['/usr/bin/ssh','-NT','-F','/dev/null','-i',str(root/'private/arch-guest-key'),'-o','IdentitiesOnly=yes','-o','ForwardAgent=no','-o','ForwardX11=no','-o','ExitOnForwardFailure=yes','-o','ServerAliveInterval=15','-o','ServerAliveCountMax=2','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(root/'private/terminal-known-hosts'),'-o','ProxyCommand=socat STDIO UNIX-CONNECT:'+str(root/'runtime/terminal-fast/io/ssh.sock'),'-R','127.0.0.1:18080:127.0.0.1:18081','matt@terminal-evolution'])
print('Open this private local URL in your browser:')
print('http://127.0.0.1:6080/open?token='+(root/'private/bmos-view-token').read_text().strip())
