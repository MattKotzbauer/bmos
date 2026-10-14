# Private daily terminal

This launch path needs the existing private BMOS lab; it is not an installer.
The repository deliberately contains no disk images, dotfiles, notes or account
credentials. The README remains empty at the owner's request.

```sh
cd /path/to/private/lab
BMOS_LAB="$PWD" python bmos/tools/launch.py
```

Open the private loopback URL printed by the launcher. If you are connected to
the lab by SSH from another computer, forward local port 6080 to the lab's
127.0.0.1:6080 first (`ssh -L 6080:127.0.0.1:6080 user@lab-host`). It displays the guest's
actual GPU-rendered Ghostty desktop through noVNC. Keep the URL private. Browser
reserved shortcuts can differ from a native viewer; fullscreen helps with layout
but does not guarantee interception of every operating-system shortcut.

The guest has its own `~/thing` copies and captured terminal/editor configuration.
Changes there do not synchronize into the host originals. The private capture
keeps editable text/source files while excluding credential paths and detected
secrets, generated logs/data, dependencies, and files over 2 MiB. Its private
manifest records exclusions; it is not a complete copy of every project or its
build dependencies. Existing guest conflicts are preserved and reviewed copies
are retained separately under `~/thing/.bmos-import-conflicts`. The daily tmux server,
editor state and Codex profile are separate from the destructive test fixtures.
The launcher never copies account credentials. In the guest terminal, use
`codex login --device-auth` to authenticate your own fresh guest account session.
The permitted HTTPS destinations go through a bounded CONNECT proxy. A service
outside the explicit allowlist will fail until deliberately added and reviewed.

Create an opaque private backup of the guest's saved notes and session files:

```sh
BMOS_LAB="$PWD" python bmos/tools/daily.py backup
```

Save and close applications before shutdown. A backup does not capture unsaved
editor buffers. For a clean guest shutdown request shutdown through the guest OS:

```sh
BMOS_LAB="$PWD" bash bmos/vm/guest.sh 'sudo systemctl stop evolution-desktop.service; sudo systemctl poweroff --no-block'
```

The VM retains its disk across shutdown. It has no arbitrary session lifetime;
CPU, memory, process and disk limits remain enforced. It does not start at host
login. Stop the project viewer and egress services when finished if desired:

```sh
systemctl --user stop bmos-viewer bmos-egress-tunnel bmos-egress
```

For build verification, save and close the daily tmux session first, then run
`BMOS_LAB="$PWD" python bmos/tools/daily.py stop`. The pipeline refuses to replace
an active daily session. Verification closes browser viewing to prevent stray
input; run the daily launcher again after the tests finish.

GPU acceleration uses virtio/virgl and the host render node. This is a virtual GPU
path, not exclusive physical GPU ownership or a bare-metal latency measurement.
No host bootloader, partition, live dotfile or desktop settings are changed.
