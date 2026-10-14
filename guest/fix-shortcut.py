"""Fix the captured idle-shell launch race in the guest copy only."""
from pathlib import Path
assert Path('/etc/os-evolution-guest').read_text().strip()=='arch-baseline'
p=Path.home()/'.local/bin/tmux-codex-shortcut.mjs';s=p.read_text()
old="tmux('send-keys', '-t', pane, 'C-c');";new="// Clear readline without a SIGINT race discarding the following command.\n    tmux('send-keys', '-t', pane, 'C-u');"
if old in s:
 assert s.count(old)==1;p.write_text(s.replace(old,new))
else:assert new in s
