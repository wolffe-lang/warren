# warren

A terminal multiplexer written in [wolf](https://github.com/wolffe-lang/wolf-lang),
for PAX first, and measured on x86-64 Linux and macOS arm64 from the first
pull request. It takes its ideas from tmux, zellij and herdr, and none of
their code.

**Status: a pure terminal core, protocol v1 codec and layout module, with a
diagnostic CLI. No working multiplexer is implemented yet.** The repository holds the pins,
tiered CI, a pinned reference emulator with a cell-for-cell harness, a survey,
recorded corpus, and reference contracts for the emulator and protocol.
`src/vt/parser.lu` decodes split UTF-8 and recognises bounded terminal
sequences; its native test entry is `src/vt_parser_test.lu`, also runnable
under lupin. The initial grid serves Unicode widths/combining marks, wide-pair
repair, cursor/erase/edit/SGR, tabs/index/scroll operations, saved cursors,
alternate-screen/reset/DEC-graphics/REP/alignment controls, bounded events,
query answers, deterministic dumps, bounded primary-history retention and
resize/reflow. Combining marks use a measured shared anchor, including
current-cell fallback at the first column. The width table is Unicode 15.1 with
explicit C-library-compatible exceptions; indicator pairs advance two cells.
Resize rows cover content/path independence, projected and
saved cursors, wide/combining glyphs, erased colour bars, alternate screens and
retained-capacity plateaus on native and lupin. `warren vt-dump` accepts raw
stdin/files and explicit recording replay. The gates compare 188 frozen corpus
streams, 113 measured anchor frames and live 200/5000-seed profiles with
bytewise/random feed boundaries and primary resize properties. Reference-report
limitations are explicit, never ignored fields or strict agreement. Assigned
scalar widths, actual 100 MB history retention and platform records have separate
measurement entries; PAX replay remains unavailable without a boot fixture.
`src/proto` implements bounded transport framing, message validation/encoding,
fragment assembly and connection-wide image acknowledgement sequencing;
[PROTOCOL](docs/PROTOCOL.md) fixes the bytes and [SERVER](docs/SERVER.md) is
the event-loop contract, with the server it describes in `src/server`.
`src/layout` holds tabs and split trees as data: their geometry, every
operation with its named refusals, and a canonical text dump
([LAYOUT](docs/LAYOUT.md)), held by hand-written goldens and seeded invariants
at five sizes. `src/client` is the terminal client ([CLIENT](docs/CLIENT.md)):
with no arguments `warren` attaches the terminal to the default session,
starting the server and the session when there are none; `warren attach -t
NAME`, `kill-server` and `list-sessions` work; `vt-dump` is a diagnostic
command.
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
| W1 | the emulator | pure core/history/reflow, diagnostic CLI and full-frame/property gates |
| W2 | one pane; detach and attach | server, terminal client and session rows on Linux, macOS and PAX under QEMU; lifecycle verbs in progress |
| W3 | panes, tabs, the bar, keys | pure layout module; compositor, keys and bar planned |
| W4 | mouse, scrollback, copy | planned |
| W5 | layouts, commands, persistence | planned |
| W6 | on the PAX image, on real hardware | planned |

## Machines and pins

| Role | Hardware / identity |
|---|---|
| Linux development witness | x86-64, rootless containers, bounded memory and pinned CPUs |
| macOS development witness | Apple Silicon arm64 |
| PAX witness | x86-64 under QEMU; real hardware at W6 |
| Compiler | wolf 0.2.40, whole release archives pinned by SHA-256 |
| Reference interpreter | lupin 0.1.62, pinned the same way |
| Standard library | wolf-std at commit `c339a471`, newer than the one the wolf archive bundles |
| Reference emulator | xterm 390 (Ubuntu `390-1ubuntu3`), binary SHA-256 pinned; run headless under Xvfb |
| Second black box | tmux 3.4 (Ubuntu `3.4-1ubuntu0.2`), binary SHA-256 pinned |
| Oracle image | Ubuntu 24.04 by digest, packages from the Ubuntu snapshot archive at `20261101T000000Z` |

`wolf-toolchain.toml` pins the archive bytes and the standard library's
commit and tree. `tools/fetch-toolchain.py` stages them into `.wolf-bin/`,
refuses anything whose digest differs, and replaces the bundled standard
library with the pinned one. `warren-oracle.toml`, `ci/packages.txt` and
`ci/oracle-binaries.lock` bind the oracle image's base, its whole package
list and each oracle binary; an image that differs in any of them is refused
before a row runs. Nothing is installed globally.

## Build and measure

```sh
bash tools/gate unit       # pins, tier planner, harness mutations, corpus digests; python3 only
bash tools/gate macos      # the above, the pinned toolchain, the build, the tests
bash tools/in-container    # Linux: builds the oracle image, holds it to its pins, runs
                           # `tools/gate linux` inside (WARREN_ENGINE=podman also works)
```

The parser's additional entries can be run after staging the tools:

```sh
root=$PWD
python3 -I tools/vt/generate_version.py # also done by tools/gate before builds
. tools/toolchain-env.sh
"$LUPIN" run src/vt_parser_test.lu
"$LUPIN" run src/vt_hostile_test.lu
"$LUPIN" run src/vt_bench_test.lu
"$WOLF" build --deny-warnings src/vt_fixture_test.lu -o target/parser-fixture
python3 -I tests/vt/parser_reference.py "$PWD/target/parser-fixture"
python3 -I tests/vt/parser_reference.py "$LUPIN" run src/vt_fixture_test.lu
```

Nineteen extra synthetic reference screens are committed under
`tests/vt/parser-reference/`. Seventeen drive a **parser projection** of
printed text and titles: sixteen agree and one uses the named D8 policy
(DEL is dropped from a title, rather than changed to `?`). The other two
measure a one-row region. Those parser projections are not whole-screen
comparisons. Current whole-frame comparisons cover eight cases, 151 census
streams and five recordings, plus the frozen 32-seed baseline. Named divergences
and source-triggered report limits have complete-frame fixtures; repaired D9/D13
reference inputs and D10's failed raw reports never become candidate-derived
goldens. The Linux drive records 200 requested-4KiB streams with bytewise/random
P2 and primary content/rendition/resize-path checks; the nightly profile uses
5000 seeds. Each rule records its source triggers, permitted field deltas and
case counts; an unexplained difference remains red. The assigned-scalar width
sweep permits zero non-control differences.
The finite hostile row uses capped
regions, and the measurement entry reports retained region charge and feed
rate separately from process startup. The [emulator contract](notes/wr00-draft-wr01-emulator.md)
defines the invariants and named reference divergences.

The gate prints one `START`/`END name exit=N` pair per step. No step skips:
a missing oracle is red.

What the Linux gate measures today is the harness, not a multiplexer:

- **Eight cases** whose expected screens are committed, three of them
  written by hand from the control-sequence document before any take. Each
  is dumped twice and both takes must be identical.
- **Three planted mutations**, on the live dumps and on the committed ones:
  a wrong attribute, a wrong cursor position and a dropped wide-character
  continuation must each go red at its own row.
- **A census of 151 small streams** that isolate one question each (what
  clears a pending wrap, what an erased cell keeps, malformed input). Their
  dumps are held by digest; `tests/vt/census.txt` is the readable form.
- **32 seeded fuzz streams** and **five recordings** (yew twice, one under
  resize; quarry; pelt with its completion menu; den's log), dumped twice and
  held by digest.
- **Session rows against tmux:** what it tells a pane, that its text and
  cursor agree with the reference on six cases, and how it sizes a session
  shared by two clients.

[SCREEN-DUMP](docs/SCREEN-DUMP.md) describes the dump, how the reference is
read, every normalisation by name, and what the mechanism cannot show.
[SURVEY](docs/SURVEY.md) and [TERM](docs/TERM.md) are the survey and the
recommendation on what programs inside are told.

The protocol-specific entry points are `src/protocol_rows.lu` (all 21 type
goldens, round trips/truncations, wide/full coverage, fragments, stale ACK,
repaint byte costs and a pure partial-write model) and
`src/protocol_fuzz.lu` (10,000 bounded deterministic malformed inputs, Linux
under a memory cap). `tests/proto/rig/` records native, checked and lupin
runs separately. `src/protocol_test.lu` puts the compact real-codec rows in
the ordinary `wolf-test` gate; `src/protocol_small.lu` is their explicit
checked/lupin entry point. Live socket/pty and renderer/model-cell comparisons belong
to the [one-pane implementation contract](notes/wr02-draft-wr03-one-pane.md),
not to the pure codec's evidence.

Unlabelled pull requests run the unit gate. The `ci` label requests the Linux
gate, and `full-matrix` requests Linux and macOS. Pushes to `trunk`, the
nightly run and a manual dispatch run everything.

## Layout

| Path | What |
|---|---|
| `src/vt/` | the emulator: parser, grid, scrollback (pure) |
| `src/proto/` | the wire protocol's frames (pure) |
| `src/layout/` | tabs and the split tree: geometry and operations ([LAYOUT](docs/LAYOUT.md)) (pure) |
| `src/server/` | the server and its event loop (not implemented) |
| `src/server_model/` | pure connection transitions/actions, without I/O |
| `src/client/` | the client: input parser and renderer |
| `src/cmd/` | `warren <verb>` and the command dispatcher |
| `src/config/` | the configuration and layout files |
| `tools/oracle/` | the reference emulator's driver, the dump format and comparison |
| `tools/corpus/` | the pty recorder and the seeded fuzz generator |
| `tools/session/` | session rows against tmux |
| `tests/vt/`, `tests/corpus/` | cases, the census, recordings, digests |
| `notes/` | emulator, protocol and implementation contracts |

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
any operating-system kernel.

Organisation-owned terminal/session programs may be consulted without
opening a kernel implementation. PAX readiness is read from its public
probe notes and black-box results.
[SOURCES](docs/SOURCES.md) records what was actually consulted.

## Licence

GPL-3.0-or-later with the wolf Training Data Permission.
See `LICENSE` and `LICENSE-TRAINING-DATA`.
