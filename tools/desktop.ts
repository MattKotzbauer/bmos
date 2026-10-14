// Private, loopback-only noVNC bridge. No host desktop/display connection.
import {createConnection} from 'node:net';
import {readFileSync,existsSync} from 'node:fs';
import {resolve,join,extname} from 'node:path';
const root=process.env.BMOS_LAB;
if(!root)throw Error('BMOS_LAB required');
const token=readFileSync(join(root,'private/bmos-view-token'),'utf8').trim();
if(token.length<40)throw Error('Expected a private random viewer token');
const assets=join(root,'artifacts/bmos-viewer/noVNC-1.7.0');
const origin='http://127.0.0.1:6080';
const html=`<!doctype html><html><head><meta charset="utf-8"><meta name="referrer" content="no-referrer"><title>BMOS terminal</title><style>body{margin:0;background:#171922;color:white;font:14px sans-serif}nav{height:32px;display:flex;align-items:center;gap:12px;padding:0 12px}#screen{height:calc(100vh - 32px)}button{cursor:pointer}</style></head><body><nav><strong>BMOS</strong><span id="status">Connecting…</span><button id="full">Full screen</button><button id="ctrl">Ctrl</button><button id="esc">Esc</button><button id="leave" title="Ctrl+Alt+Shift+Q — keep VM sessions running">Leave VM</button><button id="reconnect" hidden>Return to VM</button></nav><div id="screen"></div><script type="module">
import RFB from '/novnc/core/rfb.js';
const status=document.querySelector('#status');
const rfb=new RFB(document.querySelector('#screen'),'ws://127.0.0.1:6080/vnc');
let leaving=false;
rfb.scaleViewport=true;rfb.resizeSession=false;
rfb.addEventListener('connect',()=>status.textContent='Connected');
rfb.addEventListener('disconnect',()=>{
  status.textContent=leaving?'Left VM — sessions are still running.':'Disconnected';
  for(const id of ['full','ctrl','esc','leave'])document.getElementById(id).disabled=true;
  document.querySelector('#reconnect').hidden=false;
});
function leave(){
  leaving=true;
  // Release modifiers before closing the transport, including shortcut keys.
  for(const [key,code] of [[0xffe1,'ShiftLeft'],[0xffe2,'ShiftRight'],[0xffe3,'ControlLeft'],[0xffe4,'ControlRight'],[0xffe9,'AltLeft'],[0xffea,'AltRight']])rfb.sendKey(key,code,false);
  rfb.blur();rfb.disconnect();
  if(document.fullscreenElement)document.exitFullscreen();
}
window.addEventListener('keydown',event=>{
  if(event.ctrlKey&&event.altKey&&event.shiftKey&&event.code==='KeyQ'){
    event.preventDefault();event.stopImmediatePropagation();leave();
  }
},true);
document.querySelector('#leave').onclick=leave;
document.querySelector('#reconnect').onclick=()=>location.reload();
document.querySelector('#full').onclick=()=>document.documentElement.requestFullscreen();
document.querySelector('#esc').onclick=()=>rfb.sendKey(0xff1b,'Escape');
document.querySelector('#ctrl').onclick=()=>{rfb.sendKey(0xffe3,'ControlLeft',true);setTimeout(()=>rfb.sendKey(0xffe3,'ControlLeft',false),1000)};
</script></body></html>`;
Bun.serve<{socket:any}>({hostname:'127.0.0.1',port:6080,
 async fetch(request,server){
  const u=new URL(request.url);
  if(request.headers.get('host')!=='127.0.0.1:6080')return new Response('Invalid host',{status:403});
  if(u.pathname==='/open'&&u.searchParams.get('token')===token)return new Response(null,{status:303,headers:{Location:'/', 'Set-Cookie':`bmos=${token}; HttpOnly; SameSite=Strict; Path=/`,'Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
  if(!request.headers.get('cookie')?.split(';').some(v=>v.trim()===`bmos=${token}`))return new Response('Open the private URL printed by the launcher.',{status:401});
  if(u.pathname==='/vnc'){
   if(Bun.spawnSync(['flock','-n',join(root,'runtime/bmos-pipeline.lock'),'true']).exitCode!==0)return new Response('Build verification is active; reconnect when it finishes.',{status:503});
   if(request.headers.get('origin')!==origin)return new Response('Invalid origin',{status:403});
   return server.upgrade(request,{data:{socket:null}})?undefined:new Response('WebSocket required',{status:400});
  }
  if(u.pathname==='/')return new Response(html,{headers:{'Content-Type':'text/html','Cache-Control':'no-store','Referrer-Policy':'no-referrer'}});
  if(u.pathname.startsWith('/novnc/')){
   const file=resolve(assets,'.'+decodeURIComponent(u.pathname.slice(6)));
   if(!file.startsWith(assets+'/')||!['.js','.css','.svg','.png'].includes(extname(file))||!existsSync(file))return new Response('Not found',{status:404});
   return new Response(Bun.file(file));
  }
  return new Response('Not found',{status:404});
 },
 websocket:{
  maxPayloadLength:1024*1024,
  open(ws){
   const socket=createConnection({path:join(root,'runtime/terminal-fast/io/vnc.sock')});ws.data.socket=socket;
   socket.on('data',data=>{if(ws.send(data)===-1)socket.pause()});socket.on('error',()=>ws.close());socket.on('close',()=>ws.close());
  },
  message(ws,data){if(typeof data!=='string')ws.data.socket.write(Buffer.from(data));},
  drain(ws){ws.data.socket?.resume()},
  close(ws){ws.data.socket?.destroy()}
 }
});
console.log('BMOS viewer listening on loopback port 6080; authentication required.');
