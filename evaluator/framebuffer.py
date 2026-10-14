"""Read QEMU's external VNC framebuffer, including EGL scanout readback.

No guest screenshot API. Raw RFB pixels; private Unix socket, no host listener.
QEMU 8.2's screendump excludes SCANOUT_TEXTURE although EGL provides VNC pixels.
"""
import socket, struct, select, time
from pathlib import Path
from PIL import Image

class Framebuffer:
    def __init__(self):
        self.socket=socket.socket(socket.AF_UNIX)
        self.socket.settimeout(5)
        self.socket.connect(str(Path(__import__('os').environ['BMOS_LAB'])/'runtime/terminal-fast/io/vnc.sock'))
        assert self.read(12)==b'RFB 003.008\n'
        self.socket.sendall(b'RFB 003.008\n')
        count=self.read(1)[0]
        assert 1 in self.read(count), 'Private VNC must offer None authentication'
        self.socket.sendall(b'\x01')
        assert self.read(4)==b'\0'*4
        self.socket.sendall(b'\x01')
        header=self.read(24)
        self.width,self.height=struct.unpack('>HH',header[:4])
        self.name=self.read(struct.unpack('>I',header[20:])[0]).decode()
        # 32 bpp little-endian truecolour; bytes B,G,R,padding.
        pixel=struct.pack('>BBBBHHHBBBxxx',32,24,0,1,255,255,255,16,8,0)
        self.socket.sendall(b'\0\0\0\0'+pixel)
        self.socket.sendall(struct.pack('>BBHii',2,0,2,0,-223))
        self.canvas=Image.new('RGB',(self.width,self.height))
        self.started=False
        self.last_update=None

    def read(self,n):
        result=bytearray()
        while len(result)<n:
            chunk=self.socket.recv(n-len(result))
            if not chunk: raise EOFError('QEMU framebuffer disconnected')
            result.extend(chunk)
        return bytes(result)

    def request(self,incremental):
        self.socket.sendall(struct.pack('>BBHHHH',3,int(incremental),0,0,self.width,self.height))

    def capture(self):
        if not self.started:
            self.request(False)
            self.started=True
        elif not select.select([self.socket],[],[],.005)[0]:
            return self.snapshot
        while True:
            kind=self.read(1)[0]
            if kind==2: continue
            if kind==3:
                header=self.read(7);self.read(struct.unpack('>I',header[3:])[0]);continue
            assert kind==0,kind
            count=struct.unpack('>H',self.read(3)[1:])[0]
            resized=False
            for _ in range(count):
                x,y,w,h,encoding=struct.unpack('>HHHHi',self.read(12))
                if encoding==-223:
                    self.width,self.height=w,h
                    self.canvas=Image.new('RGB',(w,h));resized=True
                else:
                    assert encoding==0,encoding
                    data=self.read(w*h*4)
                    self.canvas.paste(Image.frombytes('RGB',(w,h),data,'raw','BGRX'),(x,y))
            self.last_update=time.perf_counter()
            # One outstanding request. Unchanged pixels come from the last real
            # server update, exactly as in an ordinary VNC viewer.
            self.request(not resized)
            if resized:continue
            self.snapshot=self.canvas.copy()
            return self.snapshot

    def close(self): self.socket.close()

if __name__=='__main__':
    import sys,time
    frame=Framebuffer(); start=time.perf_counter()
    frame.capture().save(sys.argv[1]);print(time.perf_counter()-start)
    frame.close()
