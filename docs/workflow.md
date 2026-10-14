# Build-to-verification contract

The primary measurement starts before source synchronization and includes guest
build, deployment, activation or reboot, live-artifact verification, the complete
graphical suite, and evidence completion. A previous 19-second warm suite is not
a claim that a clean build or kernel rebuild takes 19 seconds.

Run with an existing private lab:

```sh
BMOS_LAB=/path/to/private/lab bun bmos.ts recipes/tmux.json
```

Source files must be Git-tracked. Modified tracked bytes are transferred into a
managed guest build directory; unchanged outputs remain available to the native
incremental build system. Build/deploy/verify commands in recipes execute inside
the isolated guest. No recipe build command executes on the host. Application
recipes must establish that the running process uses the deployed artifact;
kernel recipes must establish the running kernel's identity after a real reboot.

The graphical evaluator sends QEMU keyboard events and reads its external VNC
framebuffer. Reviewed images and native/file outcomes are both mandatory. Frozen
rendering, wrong input, and wrong program output are negative controls. Slow cases
remain in the contract. Timings are observed virtual-screen bounds, not physical
monitor measurements. The 20-second budget is an objective and a failing gate,
not a guarantee for arbitrary rebuilds.

Private dependencies are intentionally not published: captured configuration,
reviewed screenshots, guest images, keys, notes, account state, and measurements.
The current evaluator binds to the private terminal lab described by BMOS_LAB;
this repository is not yet a stand-alone image distribution. The top-level README
is intentionally empty.

Publication uses an explicit path allowlist and credential scanning. Never push
an existing private lab's Git history into this public repository.

The checked-in `vm/` scripts are the actual rootless QEMU launcher, private SSH
transport, readiness check and live isolation audit. They intentionally preserve
the audited Intel render-node and two-CPU/two-GiB guest profile. They require the
private lab's pinned parent images, seed image and generated guest SSH identity;
none of those private artifacts is distributed here. `guest/` contains the
kernel deployment and daily-session helpers. A kernel source/configuration
change uses `recipes/linux.json`, performs a real boot and checks running kernel
notes against the linked artifact before any graphical pass is accepted.

The bounded kernel build retains x86 decoder self-tests. On the pinned guest,
`GAWK_GNU_MATCHERS=1` produced the exact same full 439 MB disassembly-formatting
output as gawk's default matcher, reducing that measured stage from 183.9 to
50.2 seconds. This does not imply a 20-second kernel build. The comparison tool
is `guest/compare-awk.py`; its private evidence retains both output hashes.

The daily profile uses a separate Codex home and tmux server. Deterministic
acceptance runs use the real Codex CLI against an explicitly labelled local
model fixture. Live account authorization and live service availability are
separate daily-use checks and are never inferred from the fixture tests.

Live account qualification additionally exercised C-a launch, a real model turn
that created/read a scratch file, and C-s forking with an independent child turn.
These network-dependent checks are separate from the deterministic 70-case suite.
The keyboard driver holds Enter for 20 ms because zero-duration presses were
ignored by the live TUI; this dwell remains inside measured input time.

The HTTPS proxy additionally permits four exact regional plugin-bundle hosts
observed in the authenticated catalog. OpenAI identifies `oaiusercontent.com`
as an expected content domain in its [network guidance](https://help.openai.com/en/articles/9247338-network-recommendations-for-chatgpt-errors-on-web-and-apps).
The proxy still rejects private addresses, unlisted hosts and non-443 ports.

With two live daily Codex sessions retained in the two-GiB guest, a regression
run exceeded the unchanged five-second Codex startup limit. A subsequent run
passed all 70 cases in 24.7 seconds. The failed run is retained; startup
reliability under concurrent use and the 20-second total budget remain unmet.

For the existing private lab, run `LAB/bmos/tools/run.sh` (the local lab also has
`LAB/bmos.sh` pointing to it) and open the private URL it prints. With the VM
already running this reconnects to the existing daily applications. Bookmark
`http://127.0.0.1:6080/` after opening that authenticated link in your browser.
The viewer's **Leave VM** button or **Ctrl+Alt+Shift+Q** disconnects input/display
and exits browser fullscreen, preserving the running VM and applications.
**Return to VM** reconnects. Closing the browser tab also leaves the VM running.
This uses the documented [noVNC disconnect API](https://novnc.com/noVNC/docs/API.html#rfbdisconnect),
not a guest power-off. No host shell aliases or dotfiles are modified.
