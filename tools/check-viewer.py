"""Real headless Chrome -> noVNC keyboard -> guest shell -> displayed pixels.
Uses an isolated browser profile started by the operator, never their live one.
"""
import base64,json,os,pathlib,subprocess,time
from websockets.sync.client import connect
root=pathlib.Path(os.environ['BMOS_LAB']);evidence=root/'artifacts/bmos-viewer-results';evidence.mkdir(exist_ok=True)
port,path=(root/'private/bmos-browser/DevToolsActivePort').read_text().splitlines()[:2]
ws=connect(f'ws://127.0.0.1:{port}{path}',max_size=16*1024*1024)
serial=0;session=None
assert subprocess.check_output(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/guest.sh'),"tmux display-message -p '#{pane_current_command}'"],text=True).strip()=='bash', 'Start from an idle test shell'

def call(method,params=None):
 global serial
 serial+=1;message=dict(id=serial,method=method,params=params or {})
 if session:message['sessionId']=session
 ws.send(json.dumps(message))
 while True:
  response=json.loads(ws.recv(timeout=15))
  if response.get('id')==serial:
   assert 'error' not in response,response
   return response.get('result',{})

def value(expression):return call('Runtime.evaluate',dict(expression=expression,returnByValue=True))['result'].get('value')
try:
 target=call('Target.createTarget',dict(url='about:blank'))['targetId']
 session=call('Target.attachToTarget',dict(targetId=target,flatten=True))['sessionId']
 call('Page.enable');call('Emulation.setDeviceMetricsOverride',dict(width=1280,height=832,deviceScaleFactor=1,mobile=False))
 token=(root/'private/bmos-view-token').read_text().strip()
 call('Page.navigate',dict(url='http://127.0.0.1:6080/open?token='+token))
 deadline=time.monotonic()+20
 while time.monotonic()<deadline:
  if value("document.querySelector('#status')?.textContent")=='Connected':break
  time.sleep(.1)
 else:raise AssertionError('Actual browser did not connect to the guest display')
 call('Input.dispatchMouseEvent',dict(type='mousePressed',x=800,y=500,button='left',clickCount=1))
 call('Input.dispatchMouseEvent',dict(type='mouseReleased',x=800,y=500,button='left',clickCount=1))
 before=base64.b64decode(call('Page.captureScreenshot')['data'])
 start=time.perf_counter()
 mapping={' ':('Space',32),"'":('Quote',222),'\\':('Backslash',220),'_':('Minus',189),'\n':('Enter',13)}
 for c in "printf 'BMOS_VIEWER_OK\\n'\n":
  code,vk=mapping[c] if c in mapping else ('Key'+c.upper(),ord(c.upper()))
  shifted=c.isupper() or c=='_'
  if shifted:call('Input.dispatchKeyEvent',dict(type='keyDown',key='Shift',code='ShiftLeft',windowsVirtualKeyCode=16,modifiers=8))
  key='Enter' if c=='\n' else c
  params=dict(key=key,code=code,windowsVirtualKeyCode=vk,modifiers=8 if shifted else 0)
  call('Input.dispatchKeyEvent',dict(type='keyDown',text='\r' if c=='\n' else c,**params))
  call('Input.dispatchKeyEvent',dict(type='keyUp',**params))
  if shifted:call('Input.dispatchKeyEvent',dict(type='keyUp',key='Shift',code='ShiftLeft',windowsVirtualKeyCode=16))
 deadline=time.monotonic()+5
 while time.monotonic()<deadline:
  native=subprocess.check_output(['bash',str(pathlib.Path(__file__).resolve().parents[1]/'vm/guest.sh'),'tmux capture-pane -p'],text=True)
  if '\nBMOS_VIEWER_OK\n' in native:break
  time.sleep(.05)
 else:raise AssertionError('Browser-delivered keys did not execute the real shell command')
 time.sleep(.2)
 after=base64.b64decode(call('Page.captureScreenshot')['data']);assert after!=before
 (evidence/'browser-terminal.png').write_bytes(after)
 record=dict(browserConnected=True,realKeyboardShellCommand=True,actualShellOutput=True,screenshotChanged=True,seconds=time.perf_counter()-start,manualPixelReviewRequired=True)
 (evidence/'result.json').write_text(json.dumps(record,indent=2));print(json.dumps(record))
finally:ws.close()
