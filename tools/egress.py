"""CONNECT-only TLS egress for the private guest. No credentials or TLS interception.

Exact domains, port 443, public resolved addresses, bounded connections, loopback
listener. SSH forwards this listener to guest loopback; guest NAT stays restricted.
"""
import ipaddress,re,select,socket,socketserver,threading
ALLOWED={'api.openai.com','auth.openai.com','chatgpt.com','chat.openai.com',
         'ab.chatgpt.com','cdn.oaistatic.com','persistent.oaistatic.com',
         'github.com','api.github.com','raw.githubusercontent.com',
         'codeload.github.com','objects.githubusercontent.com',
         'registry.npmjs.org','pypi.org','files.pythonhosted.org','archive.archlinux.org'}
slots=threading.BoundedSemaphore(16)
def destination(authority):
 match=re.fullmatch(r'([a-z0-9.-]+):443',authority.lower())
 if not match or match[1] not in ALLOWED:raise ValueError('Destination not allowed')
 addresses=socket.getaddrinfo(match[1],443,type=socket.SOCK_STREAM)
 if not addresses or any(not ipaddress.ip_address(a[4][0]).is_global for a in addresses):raise ValueError('Non-public destination')
 return addresses
class Proxy(socketserver.BaseRequestHandler):
 def handle(self):
  if not slots.acquire(blocking=False):return
  remote=None
  try:
   self.request.settimeout(10);header=b''
   while b'\r\n\r\n' not in header and len(header)<16384:
    chunk=self.request.recv(1)
    if not chunk:return
    header+=chunk
   line=header.split(b'\r\n',1)[0].decode('ascii').split()
   if len(line)!=3 or line[0]!='CONNECT':raise ValueError('CONNECT required')
   addresses=destination(line[1])
   for family,kind,proto,_,address in addresses:
    remote=socket.socket(family,kind,proto);remote.settimeout(8)
    try:remote.connect(address);break
    except OSError:remote.close();remote=None
   if remote is None:raise OSError('Connection failed')
   self.request.sendall(b'HTTP/1.1 200 Connection Established\r\n\r\n')
   while True:
    ready,_,_=select.select([self.request,remote],[],[],120)
    if not ready:return
    for current in ready:
     data=current.recv(65536)
     if not data:return
     (remote if current is self.request else self.request).sendall(data)
  except (ValueError,OSError,UnicodeError):
   try:self.request.sendall(b'HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n')
   except OSError:pass
  finally:
   if remote:remote.close()
   slots.release()
class Server(socketserver.ThreadingTCPServer):
 allow_reuse_address=True;daemon_threads=True
if __name__=='__main__':
 with Server(('127.0.0.1',18081),Proxy) as server:server.serve_forever()
