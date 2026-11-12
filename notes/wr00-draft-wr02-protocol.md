# Draft for wr02: the wire protocol and the server's state machine

An outline for the lane that fixes protocol v1 before any server or client
code. Byte layouts are exact; names of fields are suggestions. Everything
here lives in `src/proto` (pure: encode and decode only) and is used by
`src/server`, `src/client` and `src/cmd`.

## 0. What the protocol must survive

Facts it is designed around, each measured or decided elsewhere:

- No file descriptor crosses the socket. The server holds every pty and
  repaints clients from its own grids (decided). PAX has no descriptor
  passing in any case.
- A PAX stream socket holds 4096 bytes in each direction. A frame larger
  than that is the normal case, so **every write is partial-write safe and
  no peer ever blocks in a write.**
- Path sockets only; no abstract names.
- A client may sit on a terminal that draws 16 colours and gives every code
  point one cell (PAX's console). The server composes what should be shown;
  the client decides how to draw it on the terminal it has.
- The server waits on pty masters, sockets, child exits and a deadline in
  one call. wolf-std does not have that call yet: **a unified wait over file
  handles, socket handles and signals, reporting every ready handle, is a
  dependency of W2** and section 5 is written against it.
- PAX has 64 thread slots and each wolf process takes two. One server, one
  client per attached terminal and one short-lived process per `warren VERB`
  is the whole budget warren may take; the server never starts a helper
  process and never a thread.

## 1. Framing

All integers are little-endian. A frame is:

```
length  u32   bytes of payload that follow the header (0 .. 1048576)
type    u8
flags   u8    bit 0: more frames of this message follow (see 1.2); others zero
payload length bytes
```

- **F1.** A receiver that reads a length over 1 MiB, an unknown type, a
  payload that does not decode exactly, or a non-zero reserved flag sends
  `BYE protocol-error` (if it can) and closes. It never skips or resyncs.
- **F2.** A sender never interleaves two frames; a frame's bytes are
  contiguous on the socket.
- **F3.** Strings are `u16 length` then UTF-8; byte strings are `u32 length`
  then bytes; lists are `u16 count` then the items. A decoder checks every
  length against what remains before allocating.
- **F4.** Decoding is total and bounded: any byte string either decodes to
  one message or is refused, in time and memory linear in its length.

### 1.1 The first frame is the version

The first frame on a connection is `HELLO`, from the client, and its payload
begins with eight bytes whose meaning is fixed for every future version:

```
magic      4 bytes  "WRN\0"
proto_min  u16      lowest version the client speaks
proto_max  u16      highest
```

The server answers `WELCOME` with the one version it chose from that range,
or `REFUSE version` naming its own range. Everything after those eight bytes,
in every frame, is defined per version. This document is version 1.

### 1.2 Large messages

A message over 1 MiB (a full frame for a very large terminal, a
`capture-pane` reply) is sent as several frames of the same type with the
`more` flag set on all but the last. Only `FRAME`, `PASTE` and `REPLY` may
use it.

## 2. Messages

Client to server:

| Type | Name | Payload | Notes |
|---|---|---|---|
| 0x01 | HELLO | the eight fixed bytes; `role u8`; `cols u16, rows u16`; `depth u8`; `features u32`; `term str`; `target str`; `flags u8`; `cwd str`; `env list<str,str>` | role 1 attach, 2 command. depth 0 none, 1 sixteen colours, 2 256, 3 24-bit. `target` names a session, empty for the default. flags bit 0: create if missing; bit 1: read-only (refused in v1) |
| 0x02 | KEY | `mods u8, kind u8, code u32` | kind 0: a code point; kind 1: a named key (arrows, Home, F1..) by number. mods: shift 1, alt 2, ctrl 4 |
| 0x03 | MOUSE | `kind u8, button u8, mods u8, col u16, row u16` | kind: press, release, motion, wheel-up, wheel-down. Cells of the client's frame, 1-based |
| 0x04 | PASTE | `bytes` | one bracketed paste, possibly in several frames |
| 0x05 | FOCUS | `gained u8` | the client's terminal gained or lost focus |
| 0x06 | RESIZE | `cols u16, rows u16` | |
| 0x07 | INPUT | `bytes` | input the client could not parse; passed to the focused pane unchanged in normal and locked mode, dropped otherwise |
| 0x08 | ACK | `seq u32` | the client has drawn frame `seq` |
| 0x09 | REDRAW | | the client's terminal can no longer be trusted (it was suspended, or wrote an error) |
| 0x0A | DETACH | | |
| 0x0B | COMMAND | `id u32; argv list<str>; cwd str; pane str` | role 2 only; `pane` is `WARREN_PANE` from the caller's environment, or empty |
| 0x0C | PING | `nonce u32` | |

Server to client:

| Type | Name | Payload | Notes |
|---|---|---|---|
| 0x81 | WELCOME | `proto u16; client u32; server_pid u32; session str; server_version str` | |
| 0x82 | REFUSE | `code u16; text str` | then the server closes |
| 0x83 | FRAME | see 2.1 | |
| 0x84 | BELL | | |
| 0x85 | CLIPBOARD | `bytes` | text for the client to offer its terminal (OSC 52), if its settings allow |
| 0x86 | TITLE | `text str` | for the outer terminal's title |
| 0x87 | BYE | `code u16; text str` | then the server closes. Codes: detached, session ended, server stopping, replaced, too slow, protocol error, too small |
| 0x88 | REPLY | `id u32; status u8; out bytes; err bytes` | role 2; the last frame of a reply has `more` clear |
| 0x89 | PONG | `nonce u32` | |

### 2.1 FRAME

A frame says what the client's terminal should show. It is cells, never
escape sequences: the client's renderer owns the escape sequences, because
only the client knows its terminal.

```
seq        u32     this frame's number; the first after WELCOME or RESIZE is 1
base       u32     0: the frame describes every cell; otherwise the frame is a
                   change to frame `base`, which is always seq - 1
cols, rows u16     the size the frame was composed for
cursor     row u16, col u16, shape u8, visible u8
runs       list of
             row u16, col u16
             rendition: flags u16, fg u32, bg u32
             cells u16         how many columns the run covers
             text str          what fills them
```

A colour is `0x00000000` default, `0x01000000 | index`, or
`0x02000000 | r<<16 | g<<8 | b`. `text` holds one grapheme per cell, a wide
character counting for two cells; when `text` is one grapheme and `cells` is
larger, it is repeated (a run of blanks, a border).

- **M1.** Frames to one client have strictly increasing `seq`. A change frame
  applies only to a client that has drawn `base`; the server sends one only
  after the `ACK` for `base`.
- **M2.** After `RESIZE`, `REDRAW`, or a session switch, the next frame has
  `base` 0 and the numbering restarts at 1.
- **M3.** A frame's runs lie inside `cols` by `rows`, do not overlap, and
  never split a wide character. A decoder refuses one that does (F1).
- **M4.** Applying frames 1..n in order yields exactly the cells the server
  composed for frame n. (The property the renderer rows hold: compose,
  encode, decode, apply to a model terminal, compare.)
- **M5.** The server keeps, per client, the last frame it sent and the
  client's last `ACK`. While a frame is unacknowledged the server sends no
  other; damage accumulates and becomes one frame when the `ACK` arrives. A
  slow client therefore gets fewer, larger frames, costs the server one
  pending frame of memory, and delays nobody else.

## 3. Input

- **I1.** The client parses its terminal's input into `KEY`, `MOUSE`,
  `PASTE`, `FOCUS` and `RESIZE`; the server encodes keys for a pane from that
  pane's own modes (cursor-key and keypad modes, the mouse protocol and
  encoding it asked for, bracketed paste). So a pane sees the encoding it
  asked for whatever terminal the client sits on: PAX's console sends F1 as
  `ESC [ [ A`; the pane receives `ESC O P`.
- **I2.** Events from one client are applied in the order received. Between
  clients the order is the server's read order; nothing else is promised.
- **I3.** The prefix, the modes and every binding are the server's. The
  client knows none of them. (One table, one hint bar, any number of
  clients.)
- **I4.** A paste is delivered to a pane whole or not at all. Inside it the
  bytes `ESC [ 2 0 1 ~` are removed, so a paste can never end its own
  bracket; to a pane that has not asked for bracketed paste, control bytes
  other than tab, CR and LF are removed.
- **I5.** Writes to a pty never block the server. Each pane has an input
  queue of 64 KiB; when it is full, further input for that pane is dropped
  and the bar says so. (A PAX pty queues 20480 bytes before its writer would
  sleep.)

## 4. The server's state machines

### 4.1 A connection

| State | Event | Action | Next |
|---|---|---|---|
| accepted | 5 s pass with no complete frame | close | closed |
| accepted | a frame that is not HELLO, or bad magic | close, no reply | closed |
| accepted | HELLO, no common version | REFUSE version | draining |
| accepted | HELLO, peer is another user (where the host can say) | close, no reply | closed |
| accepted | HELLO role attach, target missing and no create flag | REFUSE no-session | draining |
| accepted | HELLO role attach, smaller than 20 by 6 | WELCOME, BYE too-small | draining |
| accepted | HELLO role attach | create the session if asked; WELCOME; recompute the session's size; full FRAME | attached |
| accepted | HELLO role command | WELCOME | commanding |
| attached | KEY, MOUSE, PASTE, FOCUS, INPUT | route (section 3) | attached |
| attached | RESIZE | recompute the session's size; full FRAME | attached |
| attached | ACK seq | if damage is pending, send one FRAME | attached |
| attached | REDRAW | full FRAME | attached |
| attached | DETACH, or the detach key | BYE detached; recompute size | draining |
| attached | end of file or a read or write error | recompute size | closed |
| attached | outbound queue over 256 KiB of non-frame messages | BYE too-slow | draining |
| attached | its session ends | BYE session-ended | draining |
| commanding | COMMAND | run it; REPLY (possibly several) | draining |
| commanding | anything else | BYE protocol-error | draining |
| draining | outbound queue empty, or 2 s pass | close | closed |
| any | PING | PONG | same |
| any | a malformed frame | BYE protocol-error | draining |

"Recompute the session's size" is: the smallest columns and the smallest rows
over its attached clients; if that changed, resize every pane's pty and grid
through the layout, and send every attached client a full frame. With no
client the size is kept.

### 4.2 A pane

| State | Event | Action | Next |
|---|---|---|---|
| starting | pty opened, program started in a session of its own with the pty as its terminal and default signal dispositions | watch the master | running |
| starting | either fails | show the error in the pane's cells | dead |
| running | the master is readable | read up to 64 KiB; feed the emulator; write its answers back; mark the pane's cells damaged; take its events (title, bell, clipboard) | running |
| running | the master is writable and input is queued | write what it takes | running |
| running | the master reports end or error | drain what is readable | exited |
| running | the child is reaped | record its status | running, or exited once the master has ended too |
| running | close requested | close the master (the program receives a hang-up from the kernel) | closing |
| closing | the child is reaped, or 3 s pass | remove the pane from the layout | gone |
| exited | | remove the pane; a tab with no pane closes; a session with no tab ends | gone |
| dead | a key | remove the pane | gone |

- **N1.** The server sends a signal to no process. Closing a master is the
  only way it ends a program; a pane's interrupt is the byte 0x03 written to
  the pty like any other key.
- **N2.** A child starts with every signal disposition reset to default and
  nothing blocked, whatever the server itself ignores.
- **N3.** A pane's environment is the session's, with `TERM`, `COLORTERM`,
  `TERM_PROGRAM`, `WARREN` and `WARREN_PANE` set and the markers of other
  multiplexers removed.

### 4.3 The server

| State | Event | Action | Next |
|---|---|---|---|
| starting | the runtime directory is missing | create it, mode 0700 | starting |
| starting | the directory is another user's, or open to others | refuse by name, exit 1 | |
| starting | the start lock is held | exit 0: another server is starting | |
| starting | a connect to the socket path succeeds | exit 0: a server is running | |
| starting | no server answers | remove the stale path, bind, listen, release the lock | running |
| running | the listener is readable | accept; new connection in `accepted` | running |
| running | a connection or pane event | sections 4.1, 4.2 | running |
| running | child-exit signal | reap every exited child without blocking; route to panes | running |
| running | terminate signal, or `kill-server` | BYE server-stopping to all; close every master | stopping |
| running | hang-up signal | ignored | running |
| running | the last session ends | as terminate | stopping |
| running | the deadline passes | timers: frame pacing, the clock in the bar, the save debounce, connection deadlines | running |
| stopping | all children reaped and all queues empty, or 5 s pass | remove the socket path; save state | exited |

- **V1 one loop.** Each turn: one wait over the listener, every connection,
  every master, the child-exit signal and the nearest deadline; then every
  ready handle is served once, in a fixed order (signals, masters, sockets,
  listener, timers). No turn blocks anywhere but in the wait.
- **V2 fairness.** One handle is read at most 64 KiB a turn, so a pane
  printing without end cannot starve a keystroke: input is at most one turn
  behind.
- **V3 frame pacing.** Damage does not send a frame at once. A frame is
  composed when damage is at least 8 ms old or the pane has been quiet for
  2 ms, and never more often than every 8 ms per client; while a pane holds
  synchronized output (mode 2026) its damage waits, for at most 150 ms.
- **V4 nothing a client does can stop the server**: no client message
  blocks, allocates without bound (F3), or ends a pane other than through
  the bindings.
- **V5 the terminal is the client's.** The server never writes to a
  terminal. A client restores its terminal (modes, alternate screen, cursor)
  on every exit path, including `BYE`, end of file from the server, and its
  own terminate signal.

## 5. What W2 needs that does not exist yet

| Need | Where | Without it |
|---|---|---|
| one wait over file handles, socket handles and signals with a deadline, reporting every ready handle and writability | wolf-std | no single-threaded server; this is the blocking dependency |
| the peer's user id on a Unix socket | wolf-std (the kernels have it) | the directory's mode 0700 is the only boundary, as it is for tmux |
| an exclusive lock on a file, or an atomic create-if-absent | wolf-std (to check) | two servers can race at start; the stale-socket probe narrows it but does not close it |
| a per-user runtime directory, and a daemon that outlives the login that started it, on PAX | PAX (in progress) | detach does not survive logout |
| Ctrl-Space reaching a program as 0x00 at PAX's console | PAX (being fixed) | the default prefix cannot be typed there |

## 6. Rows

| Row | What it holds |
|---|---|
| encode then decode is the identity, for generated messages of every type | F3 |
| decode of random and of mutated bytes never fails unhandled, and is linear | F1, F4 |
| the eight fixed bytes of HELLO, as a golden | 1.1 |
| compose, encode, decode, apply to a model terminal: equal cells, over the emulator corpus cut into frames at random | M3, M4 |
| a model client that never acknowledges: the server's memory for it stays one frame; a second client's latency is unchanged | M5 |
| writes of every size through a 4096-byte socket, with the reader stalled at each byte | 0, I5 |
| the three state tables, each transition once, by a scripted peer on a socketpair | 4.1 to 4.3 |
| paste: the end-bracket bytes inside a paste never reach a pane | I4 |
| session rows on a pty of the suite's own: attach, detach, a second client of another size, the client killed by end of file, the server outliving it; against tmux where the behaviour is the same | 4.1 |
| the client restores its terminal on every exit path (the terminal's modes read back through the reference emulator) | V5 |

## 7. Choices made here, each with the alternative

1. **Cells in frames, not escape sequences.** The alternative, shipping
   ready-made escape sequences, makes the client trivial but puts one
   terminal's capabilities into the server; with a 16-colour, one-cell-wide
   console as the first target, the client must own drawing.
2. **Keys as events, not bytes.** The alternative, raw bytes upward, needs
   the server to parse every outer terminal's dialect per client. Unparsed
   input still has a path (`INPUT`), so nothing is lost when the parser does
   not know a sequence.
3. **Acknowledged frames.** The alternative, sending every frame and letting
   the socket buffer push back, needs the server to block or to buffer
   without bound; at 4096 bytes of socket it would block on the first frame.
4. **One socket for clients and commands,** told apart by the role in
   `HELLO`, so there is one path to protect and one accept loop.
5. **Bindings on the server.** The alternative, the client interpreting the
   prefix, makes modes per-client state and two clients' hint bars disagree.
