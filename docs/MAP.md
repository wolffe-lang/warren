# Architecture map

| Stage | Capability | State |
|---|---|---|
| W0 | pins, tiered CI, the oracle, the survey, the prediction | the repository half is here; the PAX readiness half is measured in PAX |
| W1 | `src/vt`: parser, grid, scrollback, resize; `warren vt-dump` | pure core, CLI/replay and frozen complete-frame comparisons; final measurements pending |
| W2 | server, client, protocol v1; one pane; detach and attach | pure protocol codec and server contract; I/O planned |
| W3 | split tree, tabs, modes, the hint bar, configuration v1 | pure layout module (tabs, split tree, geometry, operations) with golden and property rows; compositor, modes, bar and configuration planned |
| W4 | mouse, scrollback, copy mode, search, OSC 52 | planned |
| W5 | command socket, CLI verbs, layout files, save and restore | planned |
| W6 | static on the PAX image; rows in PAX's own suites | planned |

The incremental parser, initial grid, protocol codec and layout module are
implemented; server and client remain planned here. A statement is marked *planned* or
names its measuring rows. `src/vt_parser_test.lu` exercises parsing alone;
`vt_grid_test`, `vt_unicode_test`, `vt_ops_test`, `vt_screen_state_test`,
`vt_graphics_test`, `vt_answers_test`, `vt_history_test`, `vt_resize_test` and
`src/vt/resize_properties_rows.lu` exercise screen/retention/reflow. The resize
properties have native and lupin rows. Frozen complete-frame comparisons and
corpus-wide primary resize properties now exist; the fresh fuzz and complete
width/resource/platform evidence remain separate pending measurements.

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
| `src/vt` | yes | W1 | pure screen/history/reflow, bounded events/answers, native/lupin operation rows and complete frozen corpus comparisons with named policies |
| `src/proto` | yes | W2 | bounded framing, payload validation, encode, assembly and ACK model (`protocol_rows`, `protocol_fuzz`) |
| `src/layout` | yes | W3 | tabs and split trees, geometry (`rects`, `borders`, `pane_at`), every operation with named refusals, the canonical dump ([LAYOUT](LAYOUT.md)); 59 hand-written goldens and seeded properties at five sizes (`layout_native`, `layout_slice` on the checked machine and lupin, `layout_test`) |
| `src/server` | no | W2 | exists and compiles |
| `src/client` | no | W2 | exists and compiles |
| `src/cmd` | no | W1/W5 | bounded raw/file/stdin and recording-replay `vt-dump`; other verbs planned |
| `src/config` | no | W3 | exists and compiles |

## Three kinds of row

- **Emulator rows:** bytes in, a screen out, compared cell for cell with a
  pinned reference emulator run as a binary. Eight cases, the 151-stream census,
  five recordings and frozen baseline fuzz have complete-frame comparisons.
  Written divergences and source-proved report limitations remain named rather
  than ignored. Written resize invariants and corpus-wide primary properties
  are separate native/interpreter checks; assigned widths and fresh fuzz remain
  separately recorded measurements.
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

- The oracle rows in the table above bind the harness/reference alone. Separate
  candidate comparisons in `tests/vt/compare_suite.py`, `compare_d9.py` and
  `compare_combining.py` judge complete frames with explicit written/report
  boundaries. `warren vt-dump` is implemented; a no-argument run still prints
  the honest scaffold status for the remaining modules.
- The scaffold proves only that the pins resolve, the module tree compiles on
  the native tier, its tests pass on the checked machine and the reference
  interpreter, and the tier planner plans what the workflow runs.
- The oracle rows run on Linux only. macOS runs the unit gate, the build and
  the tests.
- Recorded digests bind the dumps to this image. A new reference version is
  a new set of digests and a reviewed diff, never an edit in passing.
- No statement about PAX is measured yet.
