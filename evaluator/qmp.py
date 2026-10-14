"""Persistent external QEMU keyboard and framebuffer transport."""
import json
from pathlib import Path
import socket
import sys
import time

import os
ROOT = Path(os.environ['BMOS_LAB'])
IO = ROOT/'runtime/terminal-fast/io'

class QMP:
    def __init__(self):
        self.socket = socket.socket(socket.AF_UNIX)
        self.socket.settimeout(5)
        self.socket.connect(str(IO/'qmp.sock'))
        self.stream = self.socket.makefile('rwb', buffering=0)
        self.greeting = json.loads(self.stream.readline())
        self.serial = 0
        self.events = []
        self.previous_key = None
        self.call('qmp_capabilities')

    def call(self, command, arguments=None):
        self.serial += 1
        identity = self.serial
        self.stream.write(json.dumps(dict(execute=command, arguments=arguments or {}, id=identity)).encode()+b'\n')
        while True:
            line = self.stream.readline()
            if not line:
                raise EOFError('QEMU disconnected')
            reply = json.loads(line)
            if 'event' in reply:
                self.events.append(reply)
                continue
            assert reply['id'] == identity, reply
            if 'error' in reply:
                raise RuntimeError(reply['error'])
            return reply['return']

    def key(self,chord):
        self.batch([chord])

    def batch(self,chords):
        aliases={'ctrl':'ctrl','alt':'alt','shift':'shift','enter':'ret','escape':'esc',
                 'backspace':'backspace','space':'spc','tab':'tab','delete':'delete'}
        if chords[0]==self.previous_key:time.sleep(.04)
        events=[]
        for chord in chords:
            names=[aliases.get(k,k) for k in chord.split('+')]
            if names[-1]=='ret':
                # A zero-duration Enter can be ignored by the live terminal TUI.
                # Include a short physical key dwell in the measured input time.
                if events:self.call('input-send-event',dict(events=events));events=[]
                for down,keys in [(True,names),(False,list(reversed(names)))]:
                    self.call('input-send-event',dict(events=[dict(type='key',data=dict(down=down,key=dict(type='qcode',data=n))) for n in keys]))
                    if down:time.sleep(.02)
            else:
                for down,keys in [(True,names),(False,list(reversed(names)))]:
                    events.extend(dict(type='key',data=dict(down=down,key=dict(type='qcode',data=n))) for n in keys)
        if events:self.call('input-send-event',dict(events=events))
        self.previous_key=chords[-1]
        time.sleep(.002)

    def text(self, text):
        plain = {' ':'spc','\n':'ret','\t':'tab','-':'minus','=':'equal','[':'bracket_left',
                 ']':'bracket_right',';':'semicolon',"'":'apostrophe',',':'comma','.':'dot',
                 '/':'slash','\\':'backslash','`':'grave_accent'}
        shifted = dict(zip('!@#$%^&*()_+{}:"<>?|~',
                           ['1','2','3','4','5','6','7','8','9','0','minus','equal',
                            'bracket_left','bracket_right','semicolon','apostrophe',
                            'comma','dot','slash','backslash','grave_accent']))
        chords=[]
        for c in text:
            if c in shifted:chord='shift+'+shifted[c]
            elif c.isascii() and c.isupper():chord='shift+'+c.lower()
            elif c in plain:chord=plain[c]
            elif c.isascii() and c.isalnum():chord=c
            else:raise ValueError(f'Use real clipboard/compose input for non-ASCII: {c!r}')
            # Bounded batches retain every physical press/release while avoiding
            # a host monitor round trip for each character. Repeats stay separate.
            if chords and (len(chords)==4 or chord==chords[-1]):
                self.batch(chords);chords=[]
            chords.append(chord)
        if chords:self.batch(chords)

    def screenshot(self):
        self.call('screendump', dict(filename='/work/frame.ppm'))
        return (IO/'frame.ppm').read_bytes()

    def close(self):
        self.stream.close(); self.socket.close()

if __name__ == '__main__':
    q = QMP()
    try:
        print(json.dumps(q.call(sys.argv[1], json.loads(sys.argv[2]) if len(sys.argv)>2 else {})))
    finally:
        q.close()
