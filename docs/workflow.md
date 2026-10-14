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
