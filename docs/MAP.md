# Architecture map

| Stage | Capability | State |
|---|---|---|
| W0 | pins, tiered CI, the oracle, the survey, the prediction | the repository half is here; the PAX readiness half is measured in PAX |
| W1 | `src/vt`: parser, grid, scrollback, resize; `warren vt-dump` | pure core, CLI/replay and frozen complete-frame comparisons; final measurements pending |
| W2 | server, client, protocol v1; one pane; detach and attach | codec, server, terminal client, lifecycle (new, attach, detach, second client, the server outliving its client); session and client rows; on an installed PAX image under QEMU a server started at the console outlives that console's logout |
| W3 | split tree, tabs, modes, the hint bar, configuration v1 | pure layout module (tabs, split tree, geometry, operations) with golden and property rows; panes and tabs in the server, the compositor's borders and focus mark, the bar's two lines (session, tabs with their marks, mode and clock; hints, prompts and messages), modes per client from the key table, the split end to end through the real client (`keys_test`, `pane_rows`, `client_rows`, SERVER.md §8); the prefix set in warren.toml (`[keys] prefix`, `config_test`, `keys_test`, `pane_rows`); turning the hint line off planned |
| W4 | mouse, scrollback, copy mode, search, OSC 52 | pane focus and tab-label clicks with SGR/legacy reports, captured border dragging and all-motion transport, wheel and key scrollback per client, drag selection copied on release, register paste, OSC 52 export of copies and warren.toml's gate on programs' writes, search in scroll mode |
| W5 | command socket, CLI verbs, layout files, save and restore | ids, targets, the verb table, `list --json`, `send-keys`, `capture-pane`, `source`, layout files (`layout save`, `layout load`, `new -l`), saved sessions and restore at start |
| W6 | static on the PAX image; rows in PAX's own suites | on an installed PAX image under QEMU: attach or create (`new -A`), the console and ssh meeting in one server, rows over ssh, starting at login and the console logout; real hardware: the rows over ssh (`tests/pax/remote_rows.py`) are ready, and no run is recorded |

The parser, the grid, the protocol codec, the layout module, the server with
panes and tabs, and the terminal client are implemented. A statement is marked *planned* or
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
| `src/vt` | yes | W1 | pure screen/history/reflow, bounded events/answers, native/lupin operation rows and complete frozen corpus comparisons with named policies; printable ASCII runs written without the per-byte parser, held equal to it over seeded streams in random chunks (`vt_fast_test` native, checked and lupin); a reused slot's emulator held to a new one after every kind of stream (`vt_reuse_test` native, checked and lupin), and every field of `Pane` and `Vt` named with what a reuse does to it (`reuse-fields`) |
| `src/proto` | yes | W2 | bounded framing, payload validation, encode, assembly and ACK model (`protocol_rows`, `protocol_fuzz`) |
| `src/layout` | yes | W3 | tabs and split trees, geometry (`rects`, `borders`, `pane_at`), every operation with named refusals, the canonical dump ([LAYOUT](LAYOUT.md)); 59 hand-written goldens and seeded properties at five sizes (`layout_native`, `layout_slice` on the checked machine and lupin, `layout_test`) |
| `src/server` | no | W2, W3 | server: runtime directory, start lock, one wait a turn, admission limits; panes and tabs, the compositor, which reads only the rows and columns each pane's emulator changed, frame pacing (`session_rows`, `pane_rows`, `compose_rows`, `compose_damage_test`, `compose_corpus_rows`, `pacing_test` native, checked and lupin; docs/SERVER.md) |
| `src/client` | no | W2 | input parser, renderer, terminal handling, attach loop, `new` (`client_input_test`, `client_render_test`, `client_rows`; docs/CLIENT.md) |
| `src/cmd` | no | W1/W5 | bounded raw/file/stdin and recording-replay `vt-dump`; ids and their one spelling, targets resolved over a snapshot, the verb table read by the command line's parser, `list --json` schema 1, all pure (`cmd_rows_test` native and lupin; [CLI](CLI.md)); persistence planned |
| `src/config` | no | W3 | the key table: modes, the default bindings, each key's step, the hint line, the key list and the command line's verbs, all pure (`keys_test` native, checked and lupin); warren.toml's settings (`config_test`), read again by `source`; a strict TOML subset (`toml.lu`) held case by case to Python's tomllib (`tests/config/toml.table`; `config_toml_test` native, checked and lupin), a text refused past 1,024 tables and values because a key is found among its table's others one by one; layout files read and written through it (`layout_file.lu`; `tests/config/layout.table`, three goldens and the round trip; [LAYOUT](LAYOUT.md)) |

## Three kinds of row

- **Emulator rows:** bytes in, a screen out, compared cell for cell with a
  pinned reference emulator run as a binary. Eight cases, the 156-stream census,
  five recordings and frozen baseline fuzz have complete-frame comparisons.
  Written divergences and source-proved report limitations remain named rather
  than ignored. Written resize invariants and corpus-wide primary properties
  are separate native/interpreter checks; assigned widths and fresh fuzz remain
  separately recorded measurements.
- **Session rows:** a scripted client on a pseudo-terminal of the suite's own,
  compared with tmux as a black box where the behaviour is comparable, and
  with a written expectation where warren differs on purpose. *Planned.*
- **PAX rows:** under QEMU. At the console: `tests/pax/console_rows.py` boots an
  image whose console runs root's shell, types command lines through COM1 and
  presses every key under test on the emulated keyboard (the prefix Ctrl-Space,
  which the console types as NUL), on BIOS and UEFI with a USB and a PS/2
  keyboard; it reads the console's screen by replaying COM1's bytes through
  warren's own emulator. It holds `new`, a split, focus, detach, attach, a
  verb typed in a pane (`split-down`), `capture-pane` of another pane,
  `kill-server`, and a session saved and made again with each pane in its own
  directory, at the console's 0x0 window (the documented 80x24) and at
  `COLUMNS` by `LINES`. Over an ssh session: the image's own checks. The image
  recipe is not in this repository.

Mouse rows (`mouse-*` in `pane_rows` and `client_rows`) cross SGR and legacy
outer reports with inner SGR, legacy and no reports. They hold first-gesture
consumption, relative coordinates, independent clients, wide and narrow tab
labels, inert border clicks and bar cells, captured border drags with minimum
clamps, reporting children and cross-client cancellation. `border_test` holds
pure split hits, junction ownership and subtree minimums; `mouse_transport_test`
holds all-motion setup/restore and the 1000/1002/1003/1006 filtering table.
The client input table also holds raw legacy coordinates and reports split
across reads. Snapshot rows hold a client's drawn labels while another client
renames or removes tabs; both outer encodings must target the acknowledged ids,
not live label positions. `tab_hits_test` holds exact/stale/future ACKs,
independent maps, reuse, pending-map release, zero-cell identity publication
and a full-capacity stage/ACK/reset allocation plateau. The identity-frame row
also replaces a tab without changing pixels, then clicks its newly acknowledged
identity.

Scroll rows (`scroll-*` in `pane_rows`) hold the wheel in both outer
encodings (entering, moving, leaving at the live rows, the oldest-row limit,
keys dropped while looking back), every scroll-mode key and its exits, the
wheel reaching a program that asked for reports, two clients (one looking
back on a snapshot that keeps its content in place, one live), and the
alternate screen's inert wheel. `vt_view_test` holds the window itself on
native, explicit checked and lupin: history above the live rows, the clamp at
the oldest row, a soft wrap laid again at a new width, wide and combining
glyphs, renditions, the alternate screen, eviction under a small cap, the
anchor after more output, and no retained growth over repeated fills.

Selection rows (`select-*`, `paste-bracketed` in `pane_rows`) hold a drag's
snapshot, its inverse highlight and copy on release in both outer encodings, a
plain click that copies nothing, prefix `]` pasting the register, a program
that asked for reports (plain drags its own, Shift drags selecting), the far
end clamped to the origin pane, a drag whose pane ends copying nothing from the
pane that takes its slot, two clients (the highlight one's own, the
register the session's), selecting history rows while looking back, and one
bracket pair when the program asked for bracketed paste. `vt_view_test` holds
the selected text: reading order either way round, soft-wrap joins, trailing
blanks, wide and combining glyphs, history rows, and the cap refused whole.

Clipboard rows (`clip-*`, `config-refused` in `pane_rows`; `clipboard-osc52`
and `clipboard-console` in `client_rows`) hold a copy exported only to the
client that made it and only when it takes OSC 52 writes, a program's write
kept back by default and passed with `[clipboard] programs = true` to OSC 52
clients only, a refused warren.toml named on the hint line with its setting
not applied, and the terminal client writing OSC 52 for a copy, and none at the
console. `source-*` in `pane_rows` hold `source` read live from the socket,
from `warren source FILE` and at the command line: a refused file named by
line with every setting kept, a missing FILE refused, no file the defaults,
and the start's refusal no longer told once a file is read. `config_test` holds the settings parser (defaults, comments, both
values, and each refusal by line and reason) and `client_clipboard_test` the
OSC 52 sequence, on native, explicit checked and lupin.

Search rows (`search-*` in `pane_rows`) hold `?` toward older rows with the
window moved to the match and the match drawn inverse, `n` and `N`, `/` from
the oldest window's top with a match in view leaving it in place, a match on
the live rows, a match across a soft wrap, no match said on the hint line, and
a cancelled prompt. `vt_view_test` holds the search on native, explicit
checked and lupin: both window edges, again strictly past the last match, no
match keeping the last, a soft wrap from history into the live rows, wide
glyphs and combining marks, a match no longer retained, placing (kept in view,
centred, clamped at either end), marking a match in, partly in and out of the
window, the alternate screen, and needles that do not fit. `keys_test` holds
`/ ? n N` and the search prompt.

A row that tests an interrupt writes the byte 0x03 into the pseudo-terminal.
No row sends a signal from a script.

The `quick-*` terminal-client rows hold the Alt split axes, new tabs and
pane/tab close behavior in legacy and CSI-u encodings, including intentional
repeats, ignored releases, final-session confirmation at 80 and 20 columns,
Ctrl+t/Ctrl+w passthrough and the bare-Escape deadline. The bounded
`client_keyboard_test` entry runs the input/routing table on native, the
explicit checked machine and lupin. The tab checks cross an ordered HELP/
normal-mode barrier, then require exactly three default labels, allowing only
the canonical `Z`, `+` and `!` suffixes. They reject a fourth tab and use
semantic counts for later closes, not fixed columns. `tab_labels_test` holds
the pure predicate; `late-*` rows deliberately release output from inactive
tab two after tab three exists in all three encodings.

`focus-bytes` sends prefix/action in one batch; `focus-prefix-bytes` waits
for the prefix image first. Both enforce zero unchanged emitted cells, and
their byte bounds and arithmetic are in SERVER.md.

## The oracle, as measured

| Claim | Gate step |
|---|---|
| the image is the pinned one: base, package list, binaries | `oracle-image`, `oracle-identity` |
| the reference's screen can be read cell for cell, twice the same | `oracle-cases` |
| a wrong attribute, a wrong cursor and a dropped continuation are each caught by name | `harness-mutations` (committed dumps), `oracle-mutations` (live) |
| 156 census streams dump to the recorded digests | `oracle-census` |
| the fuzz generator is stable, and its streams dump to the recorded digests | `fuzz-generator`, `oracle-fuzz` |
| the recordings are the committed bytes and dump to the recorded digests | `corpus-digests`, `oracle-corpus` |
| tmux agrees with the reference on text and cursor for six cases; its split sizes, zoom, focus ring and closed pane's program, beside warren's | `tmux-rows` |
| a reference terminal that cannot open its display, or ends on a signal before it answers, is retried once, by its cause's name; a second failure is red by that name; more retries than a display's bound are their own red, `reference-retry-rate`: the least count a binomial at the highest rate measured on hosted runners (2.5% a launch) exceeds at most once in 10,000 takes, and never under 2; the display's server keeps its state between terminals (`-noreset`): every hosted retry was on a dump's second pass, launched as the server reset behind the first | `display-retry-rows`, `display-reset-rows`, and each oracle step's last lines |

## Evidence boundaries

- The oracle rows in the table above bind the harness/reference alone. Separate
  candidate comparisons in `tests/vt/compare_suite.py`, `compare_d9.py` and
  `compare_combining.py` judge complete frames with explicit written/report
  boundaries. `warren vt-dump` is a diagnostic; `warren modules` lists the
  modules and their milestones.
- The server and client rows run natively on Linux and macOS; the session rows
  and the client rows also run on PAX under QEMU from a console transcript
  (docs/SERVER.md, docs/CLIENT.md).
- The oracle rows run on Linux only. macOS runs the unit gate, the build and
  the tests.
- Recorded digests bind the dumps to this image. A new reference version is
  a new set of digests and a reviewed diff, never an edit in passing.
- PAX statements are the ones docs/SERVER.md and docs/CLIENT.md mark measured
  under QEMU; none is measured on real hardware. Real hardware is witnessed in
  two ways. `tests/pax/remote_rows.py` runs over ssh: it needs no serial port,
  keeps every warren it starts in one directory, and runs nothing when the
  host's warren would not stay there. A written checklist covers the console.
  Until a run is recorded, nothing is claimed for real hardware.
