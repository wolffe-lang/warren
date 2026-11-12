# Architecture map

| Stage | Capability | State |
|---|---|---|
| W0 | pins, tiered CI, the oracle, the survey, the prediction | the repository half is here; the PAX readiness half is measured in PAX |
| W1 | `src/vt`: parser, grid, scrollback, resize; `warren vt-dump` | incremental parser implemented; grid and command planned |
| W2 | server, client, protocol v1; one pane; detach and attach | pure protocol codec and server contract; I/O planned |
| W3 | split tree, tabs, modes, the hint bar, configuration v1 | planned |
| W4 | mouse, scrollback, copy mode, search, OSC 52 | planned |
| W5 | command socket, CLI verbs, layout files, save and restore | planned |
| W6 | static on the PAX image; rows in PAX's own suites | planned |

The incremental parser and protocol codec are implemented; the screen grid,
server and client remain planned here. A statement is marked *planned* or
names its measuring rows. `src/vt_parser_test.lu` exercises the parser without
a grid.

## The frame

```
 client (one per attached terminal)            server (one per user)
 +-------------------------------+   unix     +------------------------------------------+
 | raw tty in  -> key/mouse parse|--socket--> | sessions - tabs - split tree - panes     |
 | frames in   -> diff to tty    |<-----------| pane: pty master + emulator grid + scroll|
 +-------------------------------+            | compositor: grids + borders + bar > frame|
        `warren <verb>` (command client) ---> | command dispatcher (same socket, framed) |
                                              +------------------------------------------+
```

- **The server** owns every pty master, one emulator grid and scrollback per
  pane, the layout tree, the compositor and the clients. It is one event loop
  with no threads. *Planned.*
- **The client** owns its terminal in raw mode, the alternate screen, the
  input parser (keys, SGR mouse, bracketed paste, focus events, the size) and
  a renderer that applies the server's frames as minimal escape sequences. A
  client that dies leaves the session intact. *Planned.*
- **The wire protocol** is length-framed and versioned from its first byte.
  [PROTOCOL](PROTOCOL.md) fixes the bytes; the pure codec is exercised by
  `src/protocol_rows.lu` and the bounded Linux `src/protocol_fuzz.lu` row.
  [SERVER](SERVER.md) is the event-loop contract, not a running server.
- **The compositor** renders each pane's grid into a client's frame with
  borders, the tab bar and the hint bar, and tracks damage so that a keystroke
  repaints cells, not screens. *Planned.*

## Modules

| Module | Pure | Milestone | Measured today |
|---|---|---|---|
| `src/vt` | yes | W1 | exists and compiles (`build`, `wolf-test`, `lupin-pure`) |
| `src/proto` | yes | W2 | bounded framing, payload validation, encode, assembly and ACK model (`protocol_rows`, `protocol_fuzz`) |
| `src/layout` | yes | W3 | exists and compiles |
| `src/server` | no | W2 | exists and compiles |
| `src/client` | no | W2 | exists and compiles |
| `src/cmd` | no | W5 | exists and compiles |
| `src/config` | no | W3 | exists and compiles |

## Three kinds of row

- **Emulator rows:** bytes in, a screen out, compared cell for cell with a
  pinned reference emulator run as a binary. *Planned for W1; the harness is
  W0's.*
- **Session rows:** a scripted client on a pseudo-terminal of the suite's own,
  compared with tmux as a black box where the behaviour is comparable, and
  with a written expectation where warren differs on purpose. *Planned.*
- **PAX rows:** under QEMU, at the console and over an ssh session. *Planned.*

A row that tests an interrupt writes the byte 0x03 into the pseudo-terminal.
No row sends a signal from a script.

## The oracle, as measured

| Claim | Gate step |
|---|---|
| the image is the pinned one: base, package list, binaries | `oracle-image`, `oracle-identity` |
| the reference's screen can be read cell for cell, twice the same | `oracle-cases` |
| a wrong attribute, a wrong cursor and a dropped continuation are each caught by name | `harness-mutations` (committed dumps), `oracle-mutations` (live) |
| 151 census streams dump to the recorded digests | `oracle-census` |
| the fuzz generator is stable, and its streams dump to the recorded digests | `fuzz-generator`, `oracle-fuzz` |
| the recordings are the committed bytes and dump to the recorded digests | `corpus-digests`, `oracle-corpus` |
| tmux agrees with the reference on text and cursor for six cases | `tmux-rows` |

## Evidence boundaries

- Every row above measures the harness and the reference emulator. There is
  no grid of warren's to compare yet. `src/vt/parser.lu` is the incremental
  parser; `src/vt/vt.lu` remains a scaffold.
- The scaffold proves only that the pins resolve, the module tree compiles on
  the native tier, its tests pass on the checked machine and the reference
  interpreter, and the tier planner plans what the workflow runs.
- The oracle rows run on Linux only. macOS runs the unit gate, the build and
  the tests.
- Recorded digests bind the dumps to this image. A new reference version is
  a new set of digests and a reviewed diff, never an edit in passing.
- No statement about PAX is measured yet.
