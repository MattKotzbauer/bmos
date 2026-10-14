"""QEMU keyboard -> real apps -> external rendered pixels + read-only outcomes.

Record creates UNQUALIFIED calibration. Acceptance requires separately reviewed
immutable references. Timings cover setup, actions, capture, checks and teardown.
"""
import argparse, ast, hashlib, json, subprocess, time, sys, traceback, re, os
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw
import zstandard
from concurrent.futures import ThreadPoolExecutor
from qmp import QMP
from framebuffer import Framebuffer

ROOT=Path(os.environ['BMOS_LAB'])
HERE=ROOT/'candidates/terminal-fast'
GUEST=HERE/'guest.sh'
parser=argparse.ArgumentParser();parser.add_argument('--record',action='store_true');parser.add_argument('--fault',choices=['wrong-input','frozen-compositor','wrong-program']);args=parser.parse_args()
start=time.perf_counter()
space=os.statvfs(ROOT)
assert space.f_bavail*space.f_frsize >= 100.5*1024**3, "Preserve the 100 GiB host reserve"
out=HERE/'evidence'/('calibration-' if args.record else 'run-')/str(time.time_ns())
out.mkdir(parents=True)
gold=HERE/'references'
if not args.record:
    manifest=json.loads((gold/'REVIEWED.json').read_text())
    for reference in manifest['references']:
        assert hashlib.sha256((gold/(reference['name']+'.ppm')).read_bytes()).hexdigest()==reference['sha256'],reference['name']

subprocess.run(['bash',str(GUEST),'python /home/matt/eval/terminal-fast/prepare-scene.py'],check=True,stdout=subprocess.DEVNULL)
observer=subprocess.Popen(['bash',str(GUEST),'python /home/matt/eval/terminal-fast/observer.py'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,text=True,bufsize=1)
writer=ThreadPoolExecutor(max_workers=1);pending=[]
compressor=zstandard.ZstdCompressor(level=1)
def write_frame(name,img):
    data=f"P6\n{img.width} {img.height}\n255\n".encode()+img.tobytes()
    target=out/(name+".ppm.zst");target.write_bytes(compressor.compress(data))
    return dict(frame=target.name,frameSha256=hashlib.sha256(data).hexdigest())

q=QMP();frame=Framebuffer();results=[];images=[];last_observations={};frozen=False;failed_step=None
observation_cache=None
def checked(predicate):
    global observation_cache
    observation_cache={}
    try:return bool(predicate())
    finally:observation_cache=None

def observe(kind='nvim',**kwargs):
    key=json.dumps([kind,kwargs],sort_keys=True)
    if observation_cache is not None and key in observation_cache:return observation_cache[key]
    observer.stdin.write(json.dumps(dict(kind=kind,**kwargs))+'\n');observer.stdin.flush()
    reply=json.loads(observer.stdout.readline())
    last_observations[kind]=reply
    result=reply.get('result') if reply['ok'] else None
    if observation_cache is not None:observation_cache[key]=result
    return result

def keys(*names):
    for name in names:q.key(name)
def type_(text):q.text(text)
def rename_symbol():
    type_(' rn')
    deadline=time.perf_counter()+2
    while time.perf_counter()<deadline:
        state=observe()
        if state and state['mode']=='c':break
        time.sleep(.01)
    else:raise AssertionError('Actual LSP rename prompt did not open')
    keys('ctrl+u');type_('amount\n')

def command(text):q.key('escape');q.text(':'+text);q.key('enter')
def tmuxcheck(text=None,panes=None,windows=None,zoom=None):
    s=observe('tmux')
    return s and (text is None or text in s['text']) and (panes is None or len(s['panes'].splitlines())==panes) and (windows is None or len(s['windows'].splitlines())==windows) and (zoom is None or s['windows'].splitlines()[0].endswith('\t'+str(zoom)))
def nvcheck(lines=None,mode=None,row=None,wins=None,name=None):
    s=observe()
    return s and (lines is None or s['lines']==lines) and (mode is None or s['mode']==mode) and (row is None or s['cursor'][0]==row) and (wins is None or len(s['windows'])==wins) and (name is None or s['name'].endswith(name))

def normalized(image,name):
    image=image.copy()
    # Only wall-clock text is variable; pane titles and app pixels stay visible.
    draw=ImageDraw.Draw(image)
    draw.rectangle((1080,46,1279,68),fill='black')
    if name in ['codex-fork-split','codex-fork-copy-id']:
        # Per-run native UUID and wall-time annotation; checked separately in rollout.
        draw.rectangle((850,360,1230,385),fill='black')
        draw.rectangle((660,550,930,575),fill='black')
    if name.startswith(('cp-','debug-')) or name=='editor-return':
        draw.rectangle((535,725,746,779),fill='black') # Ghostty clipboard toast edge
    if name in ['cp-run','cp-select-result']:
        # Measured program runtimes vary; preserve DONE/CORRECT, stdin and output.
        draw.rectangle((1100,90,1279,153),fill='black')
        # Generated buffer IDs have no user semantics; result text stays visible.
        for box in [(1090,280,1113,300),(910,488,933,510),(1110,488,1133,510)]:draw.rectangle(box,fill='black')
    if name in ['debug-start','debug-step-into']:
        # ASLR/register values vary; retain variable n=3 and register labels.
        draw.rectangle((1175,235,1279,322),fill='black')
    if name=='codex-real-tool':
        for box in [(660,128,930,154),(660,380,930,408),(660,632,930,660)]:draw.rectangle(box,fill='black')
    if name=='codex-fork-submit':
        # Final transcript scrolls; per-run UUID and elapsed-time annotations only.
        draw.rectangle((850,185,1230,218),fill='black')
        draw.rectangle((660,380,930,408),fill='black')
        draw.rectangle((660,632,930,660),fill='black')
    return image

def step(name,action,predicate,roi=(0,90,1280,762),timeout=3):
    global frozen,failed_step
    if name.startswith(('cp-','debug-')) or name=='editor-return':roi=(0,90,1280,730)
    if not args.record:
        spec=next(r for r in manifest['references'] if r['name']==name)
        assert list(roi)==spec['roi'],'Unreviewed ROI change: '+name
    last_observations.clear()
    if name=='insert-text' and args.fault=='frozen-compositor':
        subprocess.run(['bash',str(GUEST),'kill -STOP $(pgrep -u 1000 -x picom)'],check=True)
        frozen=True
    before=images[-1][1] if images else frame.capture()
    t=time.perf_counter()
    if name=='insert-text' and args.fault=='wrong-input':type_('iXYQjk')
    elif name=='cp-run' and args.fault=='wrong-program':
        type_('G$i + 1jk');action() # Edit the real program, then use the real runner.
    else:action()
    input_done=time.perf_counter()
    reference=None if args.record else normalized(Image.open(gold/(name+'.ppm')),name).crop(roi)
    last=None;state=False;attempts=0;checked_frame=None
    while time.perf_counter()-t<timeout:
        last=frame.capture();observed_at=time.perf_counter();attempts+=1
        if last is not checked_frame:
            visual=reference is None or ImageChops.difference(normalized(last,name).crop(roi),reference).getbbox() is None
            checked_frame=last
        # Avoid polling app internals while the external screen is visibly wrong.
        # The same native outcomes are still mandatory before accepting a frame.
        if visual:state=checked(predicate)
        if state and visual:
            if args.record:
                # Calibration only: allow transient app paints to settle before review.
                settle=time.perf_counter()+.18
                while time.perf_counter()<settle:last=frame.capture()
            break
    else:
        state=checked(predicate)
        failed_step=dict(name=name,state=state,visual=visual,observations=dict(last_observations),roi=roi)
        last.save(out/(name+'-FAILED.ppm'))
        raise AssertionError(f'{name}: state={state}, visual={visual}')
    elapsed=time.perf_counter()-t
    images.append((name,last))
    pending.append(writer.submit(write_frame,name,last))
    results.append(dict(name=name,seconds=elapsed,inputSeconds=input_done-t,inputToObservedFrameSeconds=observed_at-t,lastInputToObservedFrameSeconds=observed_at-input_done,captures=attempts,roi=roi,changed=ImageChops.difference(before.crop(roi),last.crop(roi)).getbbox() is not None,observations=dict(last_observations),state=state,visual='UNREVIEWED' if args.record else True))
    print(f'{name}: {elapsed:.3f}s',flush=True)

original='alpha one\nbeta two\n\ngamma three\ndelta four\n\nepsilon five\nzeta six\n\neta seven\ntheta eight'.split('\n')
try:
    if not args.record:
        source=Path(__file__).read_text()
        normalization=next(n for n in ast.parse(source).body if isinstance(n,ast.FunctionDef) and n.name=='normalized')
        assert hashlib.sha256(ast.get_source_segment(source,normalization).encode()).hexdigest()==manifest['normalizationSha256'], 'Unreviewed visual normalization change'
    step('shell-command',lambda:type_("printf 'SHELL_OK\\n'\n"),lambda:tmuxcheck(text='\nSHELL_OK\n'))
    step('nvim-open',lambda:type_('nvim notes.txt\n'),lambda:nvcheck(lines=original,name='notes.txt'))
    step('open-code-buffer',lambda:command('e target.lua'),lambda:nvcheck(name='target.lua',lines=['local total = 42','print(total)']))
    step('return-notes',lambda:command('e notes.txt'),lambda:nvcheck(name='notes.txt',lines=original))
    step('insert-text',lambda:type_('iXYZjk'),lambda:nvcheck(lines=['XYZalpha one']+original[1:],mode='n'))
    step('undo',lambda:type_('u'),lambda:nvcheck(lines=original,mode='n'))
    step('redo',lambda:keys('ctrl+r'),lambda:nvcheck(lines=['XYZalpha one']+original[1:]))
    step('save',lambda:type_(' w'),lambda:observe('file',path='/home/matt/eval/terminal-fast/workspace/notes.txt')=='XYZ'+'\n'.join(original)+'\n')
    step('paragraph-J',lambda:type_('J'),lambda:nvcheck(row=3))
    step('paragraph-K',lambda:type_('K'),lambda:nvcheck(row=1))
    step('paragraph-M',lambda:type_('M'),lambda:nvcheck(row=9))
    step('paragraph-back-three',lambda:type_('<'),lambda:nvcheck(row=1))
    step('flash-jump',lambda:(type_('sepsilon'),keys('enter')),lambda:nvcheck(row=7))
    step('return-top',lambda:type_('gg'),lambda:nvcheck(row=1))
    step('visual-indent',lambda:type_('V>'),lambda:nvcheck(lines=['    XYZalpha one']+original[1:],mode='V'))
    step('visual-unindent',lambda:type_('<'),lambda:nvcheck(lines=['XYZalpha one']+original[1:],mode='V'))
    step('clipboard-yank',lambda:(keys('escape'),type_('yy')),lambda:observe('clipboard')=='XYZalpha one\n')
    step('clipboard-paste',lambda:type_('p'),lambda:nvcheck(lines=['XYZalpha one','XYZalpha one']+original[1:]))
    step('clipboard-paste-undo',lambda:type_('u'),lambda:nvcheck(lines=['XYZalpha one']+original[1:]))
    step('vsplit',lambda:(keys('escape'),type_(' v')),lambda:nvcheck(wins=2))
    step('maximize',lambda:keys('ctrl+m'),lambda:observe().get('maximized') is True)
    step('unmaximize',lambda:keys('ctrl+m'),lambda:observe().get('maximized') is False)
    step('close-vsplit',lambda:type_(' q'),lambda:nvcheck(wins=1))
    step('telescope-files',lambda:type_(' sf'),lambda:observe().get('filetype')=='TelescopePrompt')
    step('telescope-filter',lambda:type_('target.lua'),lambda:observe().get('lines')==['> target.lua'])
    step('telescope-open',lambda:keys('enter'),lambda:nvcheck(name='target.lua',lines=['local total = 42','print(total)']))
    step('comment',lambda:type_('H'),lambda:nvcheck(lines=['-- local total = 42','print(total)']))
    step('uncomment',lambda:type_('H'),lambda:nvcheck(lines=['local total = 42','print(total)']))
    step('lsp-definition',lambda:type_('j0wwgd'),lambda:nvcheck(row=1,mode='n') and observe()['cursor'][1]==6 and 'lua_ls' in observe()['clients'])
    step('lsp-rename',rename_symbol,lambda:nvcheck(lines=['local amount = 42','print(amount)']))
    step('lsp-save',lambda:type_(' w'),lambda:observe('file',path='/home/matt/eval/terminal-fast/workspace/target.lua')=='local amount = 42\nprint(amount)\n')
    step('autopair',lambda:type_('Go('),lambda:nvcheck(lines=['local amount = 42','print(amount)','()'],mode='i'))
    step('autopair-tab',lambda:(keys('tab'),type_('jk')),lambda:nvcheck(lines=['local amount = 42','print(amount)','()'],mode='n'))
    step('buffer-next',lambda:type_('L'),lambda:nvcheck(name='notes.txt'))
    step('nvim-terminal',lambda:command('terminal'),lambda:any('[matt@evolution-baseline workspace]$' in line for line in observe().get('lines',[])),roi=(0,90,1280,300))
    step('terminal-command',lambda:type_("iprintf 'NVIM_TERM_OK\\n'\n"),lambda:'NVIM_TERM_OK' in observe().get('lines',[]),roi=(0,90,1280,300))
    step('terminal-normal',lambda:keys('escape','escape'),lambda:nvcheck(mode='nt'),roi=(0,90,1280,300))
    step('terminal-close',lambda:command('bd!'),lambda:nvcheck(name='notes.txt'))
    step('tmux-split',lambda:keys('alt+q'),lambda:tmuxcheck(panes=2,text='[matt@evolution-baseline workspace]$'),roi=(0,46,1280,770))
    step('tmux-pane-typing',lambda:type_("printf 'RIGHT_PANE_OK\\n'\n"),lambda:tmuxcheck(text='\nRIGHT_PANE_OK\n',panes=2),roi=(0,90,1280,770))
    step('tmux-left',lambda:keys('alt+h'),lambda:tmuxcheck(text='XYZalpha one',panes=2),roi=(0,69,1280,770))
    step('tmux-swap-right',lambda:keys('alt+shift+l'),lambda:observe('tmux')['panes'].splitlines()[1].split('\t')[2]=='nvim')
    step('tmux-swap-left',lambda:keys('alt+shift+h'),lambda:observe('tmux')['panes'].splitlines()[0].split('\t')[2]=='nvim')
    step('tmux-zoom',lambda:keys('alt+o'),lambda:tmuxcheck(panes=2,zoom=1))
    step('tmux-unzoom',lambda:keys('alt+o'),lambda:tmuxcheck(panes=2,zoom=0))
    step('tmux-window',lambda:keys('alt+t'),lambda:tmuxcheck(windows=2),roi=(0,46,1050,770))
    step('tmux-rename-prompt',lambda:keys('alt+r'),lambda:True,roi=(0,46,1050,69))
    step('tmux-rename',lambda:type_('work\n'),lambda:'\twork\t1\t' in observe('tmux')['windows'],roi=(0,46,1050,770))
    step('tmux-previous',lambda:keys('alt+p'),lambda:tmuxcheck(text='XYZalpha one'),roi=(0,46,1050,770))
    step('tmux-next',lambda:keys('alt+n'),lambda:'\twork\t1\t' in observe('tmux')['windows'],roi=(0,46,1050,770))
    step('codex-shortcut-start',lambda:keys('ctrl+a'),lambda:tmuxcheck(text='/review - review any changes and find issues'),timeout=5)
    step('codex-type',lambda:type_('verify terminal'),lambda:tmuxcheck(text='verify terminal'))
    step('codex-multiline',lambda:(keys('shift+enter'),type_('second line')),lambda:tmuxcheck(text='second line'))
    step('codex-submit',lambda:keys('enter'),lambda:tmuxcheck(text='LOCAL FIXTURE: terminal workflow verified.'),timeout=5,roi=(0,90,1280,500))
    step('codex-copy-id',lambda:keys('alt+c'),lambda:bool(re.fullmatch('[0-9a-f-]{36}',observe('clipboard') or '')),roi=(0,90,1280,500))
    source_id=observe('clipboard')
    step('codex-fork-split',lambda:keys('alt+shift+q'),lambda:tmuxcheck(panes=2) and 'Treat following instructions' in ' '.join(observe('tmux')['text'].split()),roi=(640,90,1280,680),timeout=8)
    step('codex-fork-copy-id',lambda:keys('alt+c'),lambda:bool(re.fullmatch('[0-9a-f-]{36}',observe('clipboard') or '')) and observe('clipboard')!=source_id,roi=(640,90,1280,680))
    fork_id=observe('clipboard')
    step('codex-fork-type',lambda:type_('child only'),lambda:tmuxcheck(text='child only'),roi=(640,650,1280,770))
    step('codex-fork-submit',lambda:keys('enter'),lambda:tmuxcheck(text='child only') and observe('tmux')['text'].count('Worked for')==2 and observe('sessions',source=source_id,fork=fork_id).get('fork_has_child') is True,roi=(640,90,1280,680),timeout=5)
    step('codex-real-tool',lambda:(type_('create fixture file'),time.sleep(.08),keys('enter')),lambda:observe('file',path='/home/matt/eval/terminal-fast/workspace/codex-created.txt')=='CODEX_TOOL_OK\n' and tmuxcheck(text='LOCAL FIXTURE: created codex-created.txt.') and observe('tmux')['text'].count('Worked for')==3,roi=(640,90,1280,730),timeout=5)
    step('editor-return',lambda:(keys('alt+1'),time.sleep(.05),keys('alt+o')),lambda:nvcheck(name='notes.txt') and tmuxcheck(text='XYZalpha one'))
    step('cp-open',lambda:command('e debug.py'),lambda:nvcheck(name='debug.py'))
    step('cp-run',lambda:type_(' cr'),lambda:len(observe()['jobs'])==3 and all(j['status'] in ['DONE','CORRECT'] and not j['running'] for j in observe()['jobs']) and observe('file',path='/home/matt/eval/terminal-fast/workspace/debug.py')=='a, b = map(int, input().split())\nprint(a + b)\n',timeout=5)
    step('cp-select-result',lambda:type_('j'),lambda:sorted(j['stdout'] for j in observe()['jobs'] if j['id']!='Compile')==['18\n','5\n'])
    step('cp-close',lambda:type_('q'),lambda:nvcheck(name='debug.py',wins=1))
    step('debug-open',lambda:command('e sample.cpp'),lambda:nvcheck(name='sample.cpp'))
    step('debug-breakpoint',lambda:type_('5G bb'),lambda:any(p['line']==5 and p['path'].endswith('/sample.cpp') for p in observe()['breakpoints']))
    step('debug-start',lambda:type_(' db'),lambda:bool(observe()['debug']) and observe()['debug']['frame'].get('line')==5,timeout=6)
    step('debug-step-into',lambda:keys('f11'),lambda:bool(observe()['debug']) and observe()['debug']['frame'].get('line') in [1,2])
    step('debug-quit',lambda:type_(' dq'),lambda:observe()['debug'] is False and nvcheck(wins=1))
except Exception as error:
    traceback.print_exc();failure=str(error)
else:failure=None
finally:
    if frozen:subprocess.run(['bash',str(GUEST),'kill -CONT $(pgrep -u 1000 -x picom)'],check=True)
    q.close();frame.close();observer.stdin.close();observer.wait(timeout=3)
    # One bounded writer overlaps disk/compression with UI waits. Completion of
    # EVERY artifact remains inside the measured invocation and budget gate.
    for result,future in zip(results,pending):result.update(future.result())
    writer.shutdown(wait=True)
    elapsed=time.perf_counter()-start
    functional_pass=not failure
    if not args.record and not failure:
        if [r['name'] for r in results] != [r['name'] for r in manifest['references']]:failure='Incomplete or reordered acceptance contract'
        elif elapsed>20:failure='Suite exceeded the 20 second performance contract'
    report=dict(failedStep=failed_step,functionalPass=functional_pass,calibration=args.record,fault=args.fault,pass_=not failure and not args.record,failure=failure,totalSeconds=elapsed,budgetSeconds=20,budgetMet=elapsed<=20,results=results,scope='terminal workflow; coverage inventory required, not universal OS parity',capture='QEMU external VNC EGL readback; host monotonic clock, includes observer overhead')
    (out/'results.json').write_text(json.dumps(report,indent=2));print(out);print('TOTAL',elapsed)
    sys.exit(1 if failure else 0)
