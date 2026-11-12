# warren

A terminal multiplexer written in [wolf](https://github.com/wolffe-lang/wolf-lang),
for PAX first, and measured on x86-64 Linux and macOS arm64 from the first
pull request. It takes its ideas from tmux, zellij and herdr, and none of
their code.

**Status: W0, the map. Nothing is implemented.** The repository holds the
pins, the module tree as compiling stubs, tiered CI, and the documents that
say what will be built and how it will be measured. The `warren` binary this
tree builds prints that it is a scaffold and exits 1.
[MAP](docs/MAP.md) separates what is planned from what is measured.

## What is planned

- **A server and clients.** One server per user owns every pseudo-terminal and
  keeps a screen for each pane; clients attach over a Unix-domain socket, are
  repainted from the server's screens, and can detach and come back. A client
  that dies leaves the session running.
- **An emulator of its own.** Each pane is a terminal emulator for the common
  subset of xterm's control sequences: cursor motion, erase, insert and delete,
  scroll regions, SGR with 256 and true colour, the alternate screen, bracketed
  paste, SGR mouse reports, UTF-8 with wide and combining characters, titles,
  cursor shapes, and the device attribute and status answers. No sixel and no
  images. Its screens are held, cell for cell, to a pinned reference emulator.
- **Panes and tabs.** A split tree inside tabs, with layouts as a declarative
  file from the start. Floating panes come later.
- **Keys you can see.** Modes with an always-visible hint bar, plus a
  configurable prefix (Ctrl-Space by default).
- **Mouse on by default,** passed through to a program that asks for reports.
- **Scrollback and copy:** per-pane scrollback under a byte cap, search, a
  keyboard copy mode, an internal buffer and OSC 52 outward.
- **One TOML file** for configuration, and a command socket so that scripts
  can drive it (`warren split`, `warren send-keys`, `warren list --json`).
- **Layouts and working directories are saved and restored.** Running programs
  are not resurrected.

| Milestone | What | State |
|---|---|---|
| W0 | the map: pins, CI, the oracle, the survey, the prediction | in progress |
| W1 | the emulator | planned |
| W2 | one pane; detach and attach | planned |
| W3 | panes, tabs, the bar, keys | planned |
| W4 | mouse, scrollback, copy | planned |
| W5 | layouts, commands, persistence | planned |
| W6 | on the PAX image, on real hardware | planned |

## Machines and pins

| Role | Hardware / identity |
|---|---|
| Linux development witness | x86-64, rootless containers, bounded memory and pinned CPUs |
| macOS development witness | Apple Silicon arm64 |
| PAX witness | x86-64 under QEMU; real hardware at W6 |
| Compiler | wolf 0.2.39, whole release archives pinned by SHA-256 |
| Reference interpreter | lupin 0.1.61, pinned the same way |
| Standard library | wolf-std at commit `77cf3210`, newer than the one the wolf archive bundles |

`wolf-toolchain.toml` pins the archive bytes and the standard library's
commit and tree. `tools/fetch-toolchain.py` stages them into `.wolf-bin/`,
refuses anything whose digest differs, and replaces the bundled standard
library with the pinned one. Nothing is installed globally.

## Build and measure

```sh
bash tools/gate unit      # pin metadata and the CI tier planner; needs python3 only
bash tools/gate linux     # the pinned toolchain, the build, the tests (or: macos)
```

The gate prints one `START`/`END name exit=N` pair per step. A step that is
skipped says so; a count of steps is never a pass.

Unlabelled pull requests run the unit gate. The `ci` label requests the Linux
gate, and `full-matrix` requests Linux and macOS. Pushes to `trunk`, the
nightly run and a manual dispatch run everything.

## Layout

| Path | What |
|---|---|
| `src/vt/` | the emulator: parser, grid, scrollback (pure) |
| `src/proto/` | the wire protocol's frames (pure) |
| `src/layout/` | tabs and the split tree (pure) |
| `src/server/` | the server and its event loop |
| `src/client/` | the client: input parser and renderer |
| `src/cmd/` | `warren <verb>` and the command dispatcher |
| `src/config/` | the configuration and layout files |

The three pure modules do no I/O. They are tested on every host and under the
reference interpreter.

## Clean room

May be read: ECMA-48; xterm's control-sequences document; the VT100, VT220 and
VT520 manuals; the terminfo(5) and termios(3) manual pages; pty(7), unix(7),
epoll(7) and signal(7); and the manuals, READMEs, changelogs and default
configuration files of tmux, zellij, screen and herdr, as documents. All of
those programs may be run as black boxes.

Never read: the source of tmux, zellij, screen, herdr, dvtm, abduco or mosh;
of any terminal emulator (xterm, alacritty, kitty, wezterm, foot, vte,
libvterm, libtsm, st); of ncurses, termwiz or the vt100 and vte crates; or of
any operating-system kernel other than PAX.

Organisation-owned code may be consulted: PAX's console and pseudo-terminals,
yew's terminal layer, pelt, burrow's session code and quarry.
[SOURCES](docs/SOURCES.md) records what was actually consulted.

## Licence

GPL-3.0-or-later with the wolf Training Data Permission.
See `LICENSE` and `LICENSE-TRAINING-DATA`.
