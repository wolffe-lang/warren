# Server state machine

This is the server's contract, and `src/server` implements it. Wire bytes
and numbered image rules are in PROTOCOL.md. The server owns one event
loop, every pty master, every emulator/grid, layout/session state, accepted
sockets, their bounded queues, child handles and the readiness set. The
client alone owns its terminal; the server never writes to it. No helper
process or server thread is part of v1.

## 1. The wait surface, the pins, and the limits

The server is built at wolf 0.2.40 with wolf-std `c339a471`
(`wolf-toolchain.toml`). That standard library serves the one wait this
loop needs: `poll.open`, `poll.add_file(mut w, master, poll.READ)`,
`poll.add_listener(mut w, listener)`, `poll.add_socket(mut w, client, interest)`,
`poll.modify`, `poll.remove`, `poll.wait(mut w, meanings, deadline_ms)` and
`poll.close`, over pseudo-terminal masters, the listener, client sockets
(READ and WRITE) and listened signals together, answering every ready entry
once with the signal meaning beside them. Ready entries carry `key` and
`facts` (`READ=1`, `WRITE=2`, `HANGUP=4`, `ERROR=8`). Keys are reused, so a
returned batch is routed through a snapshot of key-to-owner generations: an
event taken for an earlier owner of a key is discarded.

Each dependency is held by a row in `tests/deps/`, run natively and on the
checked machine on Linux and macOS and natively on PAX under QEMU (lupin
refuses each host call by name): `one_wait` (the whole set in one wait, a
signal beside the entries, a deadline never early, a hung-up master),
`partial_write` (`net.write_some` takes a prefix and answers busy; 4096 bytes
on PAX), `start_lock` (an exclusive `fs.lock`, a taken path, a stale dial),
`peer_cred` (`unix.peer_credentials`; on PAX, as the super-user, a second uid
is refused a socket inside a 0700 directory) and `daemon` (a server started
by fork and a new session outlives its starter). `src/vt_api_test.lu` holds
the emulator surface the server reads.

**Admission limits** (`src/server/limits.lu`, each a named constant):

| Limit | Value | What happens past it |
|---|---|---|
| sessions | 16 | REFUSE resource-limit (7) |
| panes in a session, across its tabs | 32 | the split or new tab is refused, named on the client's hint line |
| connections, every phase | 32 | the listener leaves the readiness set; dials wait in the backlog |
| connections before HELLO | 4 | the same |
| history per pane | 2 MiB | the oldest lines go |
| projected memory | 512 MiB | REFUSE resource-limit (7); a split or new tab is refused by name |

The projection counts every pane slot at its measured cost (six times its
history cap, both screens at its size, 1 MiB of fixed buffers; a free slot
keeps its emulator and is counted too) and each connection (one physical
frame's receive buffer, a paste assembly, the 256 KiB event queue, a 4 KiB
allowance for two fixed tab-hit maps, and, when attached, one worst-case image,
a 64-byte-a-cell shadow of what its client holds, its scroll window and that
window's scratch at the same cost a cell, and its session's 65524-byte
register, counted for every attached client as an upper bound).

Most of a pane's resident size is the emulator's history ring: it is made
whole, with a copy, when the emulator is made (16.4 MB resident for an 8 MiB
ring) and four times over at the emulator's first resize (32.8 MB more; later
resizes reuse those buffers), about six times the cap in all (warren#7). So
the cap is 2 MiB a pane in this version, and the projection counts six times
it. A ring that grows as history arrives, and a resize that keeps it, are the
emulator's to do; a larger cap comes back with them. With the 2 MiB cap a
server's resident size is about 4 MB at start on Linux, 11 MB with one 80x24
session and its client, and 6 MB more for a second (`MEASURE server-rss`);
it stays flat over 10,000 keystrokes beside a flooding pane and over 200
splits and closes (pane slots are reused, never dropped).

**On PAX**, a server takes three of the machine's 64 thread slots (its main
thread and two the runtime starts for signals and children; measured under
QEMU), and every wolf program inside a pane takes two (pax#354 is the
machine-wide limit). A Unix stream holds 4096 bytes in each direction, so a
repaint always spans several writes, and a client takes those bytes a wake
at a time: a pane that writes titles (or other events) as fast as it can
outruns every client there, and each is detached as too slow (the too-slow
row is red on PAX). Keeping the title as state, not queuing each one as an
event, would remove the title case; this version does not. Surviving a console logout depends on
pid 1 staying (pax#358, not merged): until an image with it proves the
logout case, the server's promise on PAX is that it outlives the client
process that started it.

## 2. One turn

Use `signal.listen` for child exit and termination; ignore hangup in the
server's own detached session. Read monotonic time (`time.monotonic_ns`) and
compute a relative millisecond deadline by ceiling the remaining interval;
0 looks without parking and -1 waits forever. Never pass an absolute time
as `deadline_ms`. Timer decisions still compare the monotonic clock after
the wait, which may return early for a ready entry.

Wait once. Handle the returned signal first (reap every completed child),
then ready masters, connected sockets, the listener, and expired timers.
Within each class use stable owner-id order, rotating the first owner each
turn. Serve each handle at most 64 KiB of reads, 64 KiB of writes and 64 KiB
of already-buffered parsing per turn. Socket reads/writes and accepts must
have bounded nonblocking APIs; accept only a bounded batch, and apply the
connection-memory admission limit before registering a peer. Remaining
work schedules a zero-deadline turn. No phase may run an unbounded drain
loop while a descriptor remains ready. At most one wait blocks a turn.

Enable WRITE with `poll.modify` only when an output/input queue is nonempty;
restore READ when it drains. For ptys, use `fs.read_chunk` and
`fs.write_some`, never UTF-8-decoding reads (partial characters are normal).
Only consume the count a write returns. `busy` leaves the offset unchanged;
EOF/read error closes or advances that owner, not the loop. Socket M2 must
serve the same offset algorithm. Do not cast socket-table numbers into
`fs.File`: the two runtime tables number independently.

Damage becomes a frame when at least 8 ms old or the pane is quiet for 2 ms,
never more often than every 8 ms per client. Synchronized output waits at
most 150 ms before forced publication. Use monotonic deadlines for those,
HELLO's 5 s, drain's 2 s, closing pane's 3 s, stopping server's 5 s, the
clock-bar tick and save debounce. No deadline requires a timer descriptor.
A hot master cannot prevent the socket phase or expired timers running.

## 3. Connection table

Each connection owns a socket, a readiness key/generation, one physical
receive buffer, one bounded logical assembly, a parser offset, bounded event
output and at most one image output, their write offset, sequencing state,
and the absolute deadline for its current timed state. State transitions
are transactional: validate first, then mutate session state.

| State | Event | Actions | Next |
|---|---|---|---|
| accepted | 5 s without a complete HELLO | unregister, close, free buffers | closed |
| accepted | non-HELLO or bad magic | close silently | closed |
| accepted | no version overlap | enqueue bootstrap REFUSE version | draining |
| accepted | wrong uid (when callable) | close silently | closed |
| accepted | malformed supported HELLO | close silently | closed |
| accepted | missing target without create | REFUSE no-session | draining |
| accepted | read-only option | REFUSE read-only | draining |
| accepted | attach below 20x6 | WELCOME then BYE too-small; do not create a session | draining |
| accepted | valid attach | create only if needed; WELCOME; register membership; recompute size; force full image | attached |
| accepted | valid command role | WELCOME; do not enter any size set | commanding |
| attached | KEY/MOUSE/PASTE/FOCUS/INPUT | route according to current bindings/modes and queue caps | attached |
| attached | RESIZE below minimum | remove membership; recompute; BYE too-small | draining |
| attached | valid RESIZE | update membership size; recompute ptys/grids; force full after outstanding ACK | attached |
| attached | REDRAW | force full after outstanding ACK; do not reset seq | attached |
| attached | ACK outstanding seq | release immutable image; compose pending damage when pacing permits | attached |
| attached | stale ACK <= last acknowledged | ignore, release nothing | attached |
| attached | future/unsent ACK | protocol-error if safely writable; remove membership | draining or closed |
| attached | DETACH or detach binding | remove membership; recompute; BYE detached | draining |
| attached | EOF/read/write error | remove membership; recompute; unregister/close | closed |
| attached | non-image output >256 KiB | remove membership; BYE too-slow if safe else close | draining or closed |
| attached | session ends | remove membership; BYE session-ended | draining |
| commanding | one COMMAND | bounded dispatch; one logical REPLY, possibly fragmented | draining |
| commanding | anything else except PING | BYE protocol-error if safe | draining or closed |
| attached/commanding | PING outside a fragment chain | enqueue PONG, subject to queue cap | same |
| attached/commanding | wrong-role, duplicate HELLO, malformed message/fragment chain | protocol-error if safe; remove membership | draining or closed |
| draining | writable | finish queued bytes without interleaving; ignore further input | draining |
| draining | queue empty or 2 s elapsed, EOF or write error | unregister, close, free buffers | closed |
| closed | any stale ready event | discard by generation | closed |

No BYE can interrupt a partly transmitted physical frame or logical fragment
chain. If there is no room/time to finish the current message and append a
terminal message, close immediately. Event-output overflow must not try to
append an oversized BYE to the same overflowing queue. WELCOME ordering
and the drain deadline hold even for too-small clients.

The session size is the minimum columns and independently minimum rows of
attached members. A changed size resizes each pane through layout,
`term.set_size`, emulator resize/reflow and full-image invalidation for all
members. No members means keep the previous size. Membership leaves exactly
once upon transition out of attached, not again when a draining socket
closes. Commanding/draining/accepted sockets never participate. If an
outstanding image has an old size, finish/ACK it, then send a new full image
with the next connection-wide seq. Force-full is a flag, not another queued
image. A peer without ACK holds only its own one image, never another
client's progress.

## 4. Pane table

A pane owns its master, readiness key/generation, child handle and status,
emulator, screen damage, capped scrollback, 64 KiB input queue plus offset,
and at most one closing deadline. The parent's slave copy is closed as soon
as child startup completes; retaining it prevents EOF. The child inherits
only intended descriptors. PAX has 64 thread slots and wolf processes take
two: do not launch helpers or threads for relaying, timers or reaping.

| State | Event | Actions | Next |
|---|---|---|---|
| starting | pty and session child ready | set master nonblocking; close parent's slave; register READ | running |
| starting | either startup step fails | close every acquired descriptor, retain/reap any started child; display error cells | dead |
| running | master READ | read <=64 KiB; feed raw bytes; queue emulator answers; record title/bell/clipboard events; damage cells | running |
| running | master WRITE with input pending | one bounded partial write; advance only its count; busy keeps suffix | running |
| running | child exit | nonblocking reap; record status; keep master until its remaining output ends | running or exited |
| running | EOF or terminal master error | retain all prior bytes; unregister/close master; record terminal end; do not read after EOF | exited |
| running | close binding/command | remove the pane from the layout; unregister, close master (its program hears the hangup); move the child to the reap registry; the slot is free at once | gone |
| exited | remaining output consumed | remove pane; empty tab closes; empty session ends; keep unreaped child tracked | gone |
| dead | key acknowledging failure | remove error pane; empty-session rules apply | gone |
| gone | late child exit | reap through retained registry, no owner resurrection | gone |

The draft's child-exit and master-end ordering must not cause a second
blocking read: after a read reports eof/io, it is ended. On Linux a master
whose slaves closed commonly reports `io` (EIO), on macOS `eof`; the next
implementation's host rows must assert this explicitly. Fatal read errors
also remove that master and surface an error, never busy-spin on READ.
A vanished pane may still have a child to reap: layout ownership and process
ownership end at different times. A closed pane leaves the screen at once, as
tmux's does; its child stays in the reap registry, never signalled, until it
ends or the server stops. Closing the master is the only way the
server asks a program to end; the server never sends it a signal. In
particular Ctrl-C is input byte 03 to the pty, not a signal API call. A child
that ignores hangup can outlive pane removal; show/report this limitation,
never silently add a kill fallback.

Start with `term.open_pty`, `process.command`, argument/environment setup,
`process.set_stdin`, `set_stdout`, `set_stderr`, and
`process.start_session` with the pty slave. Startup must reset signal
ignore/blocked state and inherit no unrelated masters or sockets; this is
an end-to-end row, not inferred from the function name. The pane's child
resets every meaning the runtime names and every real-time signal by its
host number. The C library's own numbers (glibc's 32 and 33) the runtime
refuses to reset (wolf-lang#1116): one the server inherited ignored stays
ignored in its panes. A hosted CI runner starts its jobs with 32 ignored;
the row names such a signal (`MEASURE pane-inherits-unresettable`) and is
red for any other. Reap using
`process.poll()` until `Change.changed` is false. A reported ended child is
already reaped and its runtime handle closed; match `Change.child.slot` to
the saved owner and retire that handle without calling `wait_status` again
(it would return `io`). A stopped child remains live and must not be marked
exited. Never use a blocking wait for an active child. The next lane must
verify these actual signatures and status accessors at its new pin.
Environment is the session's with TERM=xterm-256color, COLORTERM=truecolor,
TERM_PROGRAM=warren, TERM_PROGRAM_VERSION, WARREN and WARREN_PANE set;
remove other multiplexer markers and LINES/COLUMNS, as TERM.md specifies.

## 5. Server table

| State | Event | Actions | Next |
|---|---|---|---|
| starting | runtime directory missing | create mode 0700, verify owner and mode without following untrusted replacement | starting |
| starting | wrong owner/open permissions/unsafe path | named refusal, release owned resources, exit 1 | exited |
| starting | atomic start lock unavailable | named refusal; do not remove a possible live server's path | exited |
| starting | lock held by another starter | exit 0, let the client retry boundedly | exited |
| starting | connect to path succeeds | release own lock, exit 0 | exited |
| starting | proven stale path | unlink only owned stale socket, bind/listen, set mode 0600, open readiness set | running |
| starting | any acquired-resource failure | close/unlink only what this attempt created; release lock | exited |
| running | listener READ | accept bounded batch; apply admission budget; register accepted peers and 5 s deadlines | running |
| running | connection/master/child event | tables above | running |
| running | child signal | poll/reap every tracked completed child without waiting on live children | running |
| running | terminate/kill-server or final session ends | stop accepts; BYE server-stopping if safe; close masters; set 5 s deadline | stopping |
| running | hangup | ignored (own detached session) | running |
| running | deadline | pace frames, clock tick, debounce persistence, connection/pane timeouts | running |
| running | fatal wait error | stop accepts; best-effort cleanup as above; report failure | stopping |
| stopping | readiness/deadline | drain clients/reap boundedly; no new sessions | stopping |
| stopping | all queues empty and children reaped, or 5 s elapsed | close remaining sockets/master handles; close waiter; remove only owned path/lock; save structural state; exit | exited |

Stale-path replacement requires an exclusive atomic start lock. A failed
connect alone is not permission to unlink somebody else's live/listening
socket. The repository's older std pin does not establish an atomic locking
primitive; W2 must verify one or obtain it as a dependency. A plain
exists-then-create test is not a lock. Runtime-directory and logout behavior
on PAX must be measured after the pid-1/runtime-directory work, not inferred
from Linux. No state file may contain screen/scrollback secrets; v1 saves
only layout and working-directory metadata, not running programs.

## 6. Client terminal exit obligations

The client saves terminal mode and registers `term.restore_at_exit` before
switching raw. Track acquisition flags so partial setup unwinds only what
was actually enabled. On normal detach, BYE of every code, REFUSE, malformed
message, server EOF, socket read/write failure, terminal input EOF, terminal
output failure, startup failure and a catchable termination signal: stop
input; disable mouse/focus/bracketed-paste modes enabled by this client;
reset rendition and cursor shape/visibility; leave its alternate screen;
restore exact saved termios; close owned descriptors. On suspend, restore
before suspension and reenter/repaint on continuation; do not pretend this
is covered until the signal/terminal row exists. Error-reporting output is
after restore when possible. A terminal that is no longer writable can only
have restoration attempted and the failure surfaced.

SIGKILL and machine/process crashes cannot execute cleanup. The server has
no terminal descriptor to restore for a killed client: raw-mode restoration
on those paths is explicitly not promised. PAX's raw-mode probe measured
that a SIGKILLed client leaves its terminal raw. Catchable exits must be
held by saved/read-back termios and emulator screen-mode rows, not merely
by asserting that a cleanup function was called.

## 7. Pure models and implementation rows

`proto.AckState` is the small pure stop-and-wait model: consecutive sends,
exact ACK, ignored stale ACK, no seq reuse after image reset. The codec's
assembly model checks same-type fragment chains and aggregate bounds.
`server_model.transition(Connection, event) -> Step` is the small pure
connection-table model. It allocates no resources and executes no actions;
`Step` carries next phase, membership, an action mask and a valid flag.
The codec test module drives its branches alongside native, checked and
lupin protocol rows. Phases are 0 accepted, 1 attached, 2 commanding,
3 draining, 4 closed. Membership must equal (phase == attached), and every
transition out of attached clears it once.

Classified events (after wire/policy checks): 0 HELLO deadline, 1 bad first
frame/magic, 2 version mismatch, 3 wrong uid, 4 no-session, 5 small attach,
6 valid attach, 7 command HELLO, 8 input event, 9 valid resize, 10 exact ACK,
11 redraw, 12 detach, 13 EOF/read/write failure, 14 output overflow,
15 session ended, 16 COMMAND, 17 PING, 18 malformed/wrong-role,
19 writable, 20 queue drained, 21 drain deadline, 22 small resize,
23 read-only refusal, 24 future ACK, 25 stale ACK, 26 error while a partial
message makes BYE unsafe. Network messages must not fabricate timer events.

Action bits: 1 unregister/close/free, 2 REFUSE, 4 WELCOME, 8 join membership,
16 recompute size after a membership change or resize, 32 force-full,
64 route input, 128 BYE, 256 REPLY, 512 PONG, 1024 release acknowledged image,
2048 flush bounded output, 4096 consider paced damage, 8192 ignore. A force
full action sets a flag, not a second outstanding image. REFUSE/BYE reason
selection and actual resources stay in the event dispatcher, not this model.

The transitions are exercised through the real event dispatcher by the session
rows (`src/session_rows.lu`): a scripted client, itself wolf so that PAX runs
it too, drives a real server over its socket. Each row starts its own server
in its own runtime directory with a lifetime bound and stops it with
`kill-server`. They cover HELLO split at every byte, a bad first frame and bad
magic (closed silently), the version, no-session and read-only refusals, a
too-small attach (WELCOME then BYE, no session created), the HELLO deadline,
stale and future ACKs, a message inside a paste's fragment chain, two client
sizes converging to their minima and back, a client that never ACKs beside an
active one, detach by the prefix binding and by DETACH, Ctrl-C as the byte 03,
the last session ending the server, the command role, a second server meeting
the start lock, a pane's last output reaching its client before the session
ends (a client still owing its ACK gets the last image after that ACK, then
BYE session-ended, or the BYE alone at the closing deadline), a program that
outlives its pane being reaped, a pane's program starting with no signal
ignored or blocked and no inherited descriptor, the server's thread count, the
pre-HELLO, connection, session and memory limits (the memory row lowers the
budget through `WARREN_MEMORY_BUDGET`, which the server takes only below its
own), a resize while an image is outstanding, a client too slow for its events
beside one that keeps up, a keystroke's delay beside a flooding pane, a
flat resident size over 10,000 keystrokes, and the trace's closes (below).
`src/compose_rows.lu` holds every
composed image, applied by the client's applier, to the emulator's stored
cells, and holds the event queue's cap to the bytes a client has yet to take
(a small socket under a steady pane never empties the queue, and must not
count what it sent).

With `WARREN_TRACE` set, the server writes a trace to its standard error, and
every close of a connection names its cause there, including the closes that
send the peer nothing: `conn N closed: CAUSE`, where the cause is the message
it drained to (`REPLY sent`, `BYE 1 sent`, `REFUSE 2 sent`), the peer's end
(`end of input (closed)`), a failed write (`write failed: closed`), a first
message that is not a HELLO, a HELLO that cannot be read or is malformed, a
peer of another user, a deadline that passed (naming the phase), a message
that could not be queued, or the server stopping. A `new` at a terminal is two
connections: the command that makes the session (`REPLY sent`), then the
attach. The `close-causes` session row drives the ordinary closes, a first
message that is not a HELLO, and a client gone before its WELCOME is written,
and fails on any close in the trace that names no cause.

On PAX a pane ends when its program ends, not when the program closes its
terminal: the late-child row measures the session's end about a second after
the command there (the program's lifetime) and the server's exit right after
it, where Linux ends the session at once and the server a second
later. Either way the server does not end before the program does.

This version answers a command connection's COMMAND for `kill-server`,
`list-sessions` and `new-session [NAME]`; every other verb replies status 2
and names itself as not implemented, so a newer client facing this server
fails by name. `new-session` makes a detached session at the command HELLO's
size (80x24 when both are zero), working directory and environment, and
replies status 0 with the name on standard output. Without a NAME it takes
the lowest positive number no live session is named. A name already in use, a
size below 20x6 and a name that is not allowed reply status 1 with the reason;
a slot made between turns delays the reply by a turn, as it does a HELLO. A
pane whose program does not start is refused (REFUSE invalid-request, with the
reason) rather than shown as an error pane.

Session names are compared as bytes: no case folding and no Unicode
normalization, so two spellings of one word are two sessions. A name may hold
any bytes but `/` and the control bytes 00-1f and 7f, and may not be empty.
`new-session` refuses any other name with status 1, and an attaching HELLO
that would create a session under one gets REFUSE invalid-request; an attach
to such a name finds no session.

## 8. Panes, tabs and the frame

A session holds a layout (`src/layout`, LAYOUT.md): tabs, each a split tree
whose leaves name panes by id. Pane ids are the server's, from 1, never reused
while it runs; a pane's program reads its own as `WARREN_PANE`. The server's
pane table holds every pane of every session in reusable slots: a slot keeps
its emulator when its pane goes, and the next pane takes it after a full reset
and a resize. A slot (and its emulator) that does not exist yet is made
between turns, outside the turn's region, and the key that asked for it is
taken again on the next turn, which follows at once; the client's later input
waits behind it. Every layout operation runs inside the turn: the layout keeps
nothing of the turn's region (tabs are added, removed and renamed in place,
`src/layout_region_test.lu`).

**Sizes.** The tab area is the session's size less the bar's two lines. After
every layout operation and every change of the session's size, each pane whose
rect is not empty, in every tab, is given its rect's size: the emulator first,
then the terminal, so that the program's redraw after its window change lands
in an emulator already at the new size. A pane hidden by a small area, or by
another pane's zoom, keeps its last size and is resized when it shows again.
A zoomed pane takes the whole area. A split's new pane starts at its rect, in
the session's working directory, with the session's environment.

**Keys and modes.** Every KEY goes through the key table (`src/config/keys.lu`)
in the client's own mode; modes are per client, focus is per session. Normal
mode takes the prefix (Ctrl-Space) and four Alt quick keys:

| key | operation |
|---|---|
| `Alt+\` | split side by side, with a vertical divider |
| `Alt+\|` (`Alt+Shift+\`) | stack panes, with a horizontal divider |
| `Alt+t` or `Alt+T` | new tab |
| `Alt+w` or `Alt+W` | close the focused pane, closing its tab when empty; ask before the session's final pane closes |

Ctrl+t and Ctrl+w belong to the programs inside. The prefix hints reveal the
quick keys as `M-` chords alongside the prefix table; those quick keys also
work after the prefix. Idle still shows only `C-Space prefix`. Locked mode
passes the Alt keys through, as it does every key except its unlock key.
Other sticky modes retain their own bindings. After the prefix, one key of
its table:

| key | operation |
|---|---|
| `\|` / `-` | split the focused pane side by side / one above the other; the new pane takes focus |
| `h j k l`, arrows | focus left, down, up, right |
| `o` | focus the next pane |
| `H J K L` | move a border of the focused pane left, down, up, right (its own on that side, else the one on the other side), 2 columns or 1 row |
| `z` | zoom the focused pane, or unzoom |
| `=` | every split of the tab back to halves |
| `x` | close the focused pane, after `y` |
| `c` | a new tab |
| `n` / `p` / `1`-`9` | the next / previous tab, or the tab at that position |
| `,` | rename the tab at a prompt |
| `:` | the command line |
| `?` | the key list |
| `d` | detach |
| `w` `t` `r` `s` | pane, tab, resize and session mode |
| `g` | locked mode |
| Ctrl-Space | send Ctrl-Space (NUL) to the pane |

A key that is not in the table is dropped. The four sticky modes keep taking
their keys until Esc or Enter (Ctrl-Space goes to the prefix from them): pane
mode `| - h j k l` (and arrows) `x z o =`; tab mode `h l` (arrows, `n p`)
previous and next, `c` new, `x` close, `r` rename, `1`-`9`; resize mode `h j k
l` (arrows, `H J K L`) and `=`; session mode `d`. Locked mode passes every key
to the pane, the prefix included, and is left only with Ctrl-g. A close (`x`)
asks on the hint line; `y` closes and any other key keeps. The rename and
command prompts take printable keys, Backspace and Ctrl-u, run on Enter and are
left with Esc; confirm, the key list and the prompts go back to the sticky mode
they came from. The command line takes the table's action names and their
arguments: `split-right`, `split-down`, `focus left|right|up|down`,
`focus-next`, `resize DIRECTION [N]`, `zoom`, `equalize`, `close-pane`,
`new-tab`, `close-tab`, `next-tab`, `previous-tab`, `select-tab N`,
`rename-tab NAME`, `detach`, `lock`; an unknown verb or a bad argument is
answered on the hint line. INPUT, PASTE and mouse events reach the pane only in
normal and locked mode, and are dropped in the others.

A refused split or new tab (too small, the pane limit, the memory budget, a
program that did not start) leaves everything as it was and is named on that
client's hint line for 2 s; a focus move with no neighbour does nothing.

Alt+w closes other panes immediately but asks before the final close:
Escape or any non-yes key keeps the session, and `y` confirms. The warning
explicitly names the session, even at 20 columns.

**Closing.** A pane closes on `x` and `y` or when its program's terminal
ends; a tab closes with all its panes on `x` and `y` in tab mode; the last pane
of the last tab ends the session (as one pane did before). Keys, pastes, INPUT,
and focus reports go to the focused pane of the active tab. A mouse press
inside a shown pane focuses it. The first gesture into an unfocused pane
(press, motion and release) is consumed by the UI; later clicks in the focused
pane reach its program only when it asked for reports, relative to its rect.
The consumed gesture is tracked per client, so it does not swallow another
client's clicks. Clicking a painted tab label selects that tab, including a
wide glyph's continuation cell. Plain border clicks, overflow markers, the
session name, mode, clock and hint line stay inert. Left-dragging a border
moves the split originally hit along its own axis, with the same subtree
minimum clamps as keyboard resize. The gesture remains consumed outside the
pane area and through release; it cannot become input to a reporting child.
A different client's layout change, a key or a client resize cancels capture.
The gesture's own resizes preserve it. Chrome works in normal, locked,
prefix, pane, tab, resize and session modes; prompts, help and confirmation
own their input. Only normal and locked modes forward content mouse events.
The outer client enables all-motion reports so a child asking for 1003 can
receive hover; the server still filters 1000/1002/1003 and re-encodes 1006 or
legacy reports according to the child. When focus moves, a pane that asked for focus reports hears it lose
or take focus, and the clients take the new pane's title. A bell from the
active tab reaches the clients; titles come from the focused pane only.

**Tab hits and ACKs.** The painter's half-open display-cell spans are stored
with each connection's one immutable pending image. Only its exact, fully
sent image's ACK promotes those spans; duplicate or stale ACKs never promote
a newer map. Clicks use the last acknowledged spans, not labels recomputed
from live activity/name state. A stored id for a removed tab consumes the
gesture without selecting its successor. Mouse input waits for matching
acknowledged geometry after a size change.

There are exactly two fixed-capacity maps per connection, at most 32
scalar-only spans each. Publication and ACK overwrite those buffers in place;
promotion clears the pending map's active metadata immediately, and connection
reuse clears both maps. They retain no frame bytes or strings. If a close/
recreate batch changes tab ids but leaves all pixels and the cursor identical,
a 28-byte zero-cell v1 delta publishes the new identities for acknowledgement.
It repaints no unchanged cells; unchanged pixels and identities send nothing.

**The frame** is the session's size: the tab area, then line one of the bar
(the session's name and the tabs, the active one inverse; tabs that do not fit
leave out the far side of the active one, marked `<` or `>`; the client's mode
in a fixed field of nine columns, inverse and bold; at the right end the local
time, ` HH:MM `, from 40 columns, where narrower the mode field takes the end),
then the hint line: the mode's rows of the key table, `keys label` with the keys
inverse, two spaces apart, those that do not fit counted as `+N`. While idle
only `C-Space prefix` is shown; pressing the prefix reveals its action table,
and leaving the prefix or a mode restores the idle hint. A sticky mode keeps
its own hints until it ends. The line can instead show a
prompt with its cursor; the confirm question; or a message while one lasts.
The key list (`?`) is drawn over the tab area for that client only, one line a
binding, and scrolls with `j` and `k`.

**Scroll mode** is a client's window over one pane's retained history. Prefix
`[` opens it on the focused pane; a wheel notch up over a pane whose program
asked for no mouse reports, on its primary screen, opens it there. The window
is filled from the emulator's history ring at the pane's current width (soft
wraps, wide and combining glyphs and renditions as they were written), walking
back from the newest line only as far as it reaches, and history holds only
what is above the screen's first row, so no row shows twice. `j` and `k` (or
Down and Up) move it a row, PageDown and PageUp (or `C-f` and `C-b`) a window,
`d` and `u` half a window, `g` shows the oldest retained row and `G` the live
rows; `q`, Esc and Enter leave, and the prefix leaves for its table. The wheel
moves it three rows a notch. A window the wheel opened closes when it comes
back to the live rows; one opened with `[` stays until it is left. The window
is a snapshot: output goes on into the pane, other clients see it live, and
this client sees it on its next step, which keeps the same content in place
by its logical line and offset, or at the live rows. The pane's cursor is not
drawn over a window. A window whose pane closes ends the mode; a resized pane's
window is filled again at the new size on the same content. A window's two
buffers belong to its client and grow only between turns, outside the turn's
region: to its session's tab area once the client is attached, and to any
larger size a step asks for, which then waits for the next turn. Fills and
lookups allocate nothing.

**Selection and the register.** A left press in the focused pane in normal
mode, when its program asked for no mouse reports (with Shift, even when it
did), or in the pane a client is looking back at, may begin a selection; Alt
and Ctrl presses stay the program's. Nothing happens until the pointer moves.
The first move opens the client's window at the pane's live rows as a snapshot
(scroll mode), unless it is already looking back, so output cannot shift the
text under the drag; the selection runs in reading order from the press cell
to the pointer, clamped to the pane it started in, and is drawn inverse for
that client alone. The wheel waits while a drag is held. Release copies the
text into the session's register (soft-wrapped rows join, other rows end with a
newline, a row part's trailing blanks are dropped, a wide glyph once, combining
marks after their base) and the hint line says `copied N bytes`; more than
65524 bytes is refused whole and the register keeps its text. A window the drag
opened closes at release; one that was looking back stays. A press and release
on one cell copies nothing. Prefix `]` pastes the register into the focused
pane under PASTE's rules: one bracketed paste when the program asked for 2004,
otherwise the text with control bytes other than tab, CR and LF removed. The
register is the session's, shared by its clients, and empty when the session
starts. Each
shown pane's grid is drawn in its rect. Border cells are `│` and `─`, with
`├ ┤ ┬ ┴ ┼` where borders meet. The border cells within one cell of the
focused pane's rect are drawn in colour 2; when exactly two panes show they
share one border along its length, so the half beside the focused pane is
marked instead (tmux 3.4 draws both rules the same way, measured by its
`tmux-focus-ring` rows). A zoomed tab draws no border.

**Marks and the clock.** A tab's label carries `Z` while the tab is zoomed,
`+` once a pane of it wrote while the tab was not shown, and `!` once one rang
the bell then (the bell itself reaches clients only from the shown tab);
showing the tab clears `+` and `!`. The clock is the local time (`TZ` or
`/etc/localtime`; UTC where no zone can be read), read when the server starts
and again at each minute's boundary, which is the clock's only wake; every
session's line one is then drawn again.

**Damage.** A client's image is a delta against what it holds, over what may
have changed: the rects of the shown panes whose grids changed since its last
image, the bar's rows when they changed, and the whole frame after a layout
change (a split, a close, focus, a tab, zoom, a size), which is still a delta
unless the size changed. Output in a tab that is not shown composes nothing.
Measured on Linux (`MEASURE` in the pane rows): a focus change between two
panes side by side at 80x24 is a 600-byte image and among three panes 314
bytes; a keystroke's image holds only the focused pane's cells; a split's new
prompt is drawn 18 ms after the key; a keystroke in a split is drawn in 2.4 ms
(p50) and 13.6 ms beside a flooding neighbour in the same tab. A client's mode
change repaints only its own bar: revealing the prefix table (the mode field
and hint line) is 626 bytes at 80x24, and entering pane mode 854 bytes. Resize
mode has no idle timeout; its arrows and letter keys keep resizing until
Escape, Enter or the prefix leaves it.

The focus-byte rows distinguish two schedules at 80x24. A prefix and action
sent together retain the 600/314-byte minima and 800/500-byte bounds. When
the prefix is drawn and acknowledged first, its reveal costs
`28 + 66 + 532 = 626` bytes (fixed frame fields, mode, hints). The action
then costs `28 + 572 + 66 + 260 = 926` bytes for two panes, or
`28 + 286 + 66 + 260 = 640` for three: border, mode and hint erasure all
changed. Necessary totals are 1552 and 1266; bounds of 1720 and 1400 add
168 and 134 bytes of headroom (about 11%). Every emitted cell is checked
against the preceding image: repainting an unchanged cell fails even below
the byte bound. No tab label, session name or clock cell is repainted by
these focus changes. Optional `WARREN_FOCUS_CAPTURE=1` prints exact frame
hex and per-run attribution after the measurements.

**Rows.** `src/pane_rows.lu` drives a real server through key events: split
sizes, keys reaching the focused pane, the window change a pane's program hears
after a split, a border move, zoom and a client resize (`--winch`), the hangup
a closed pane's program hears and its reaping (`--hup`), a pane's own end,
tabs, a resize reaching a tab that is not shown, zoom, the too-small, memory and
pane-count refusals, the frame's borders and bar cell for cell, a keystroke's
image held to the focused pane's rect, the bytes of a focus change, keystrokes
in a split and beside a flooding neighbour, the time of a split, a flat
resident size over 200 splits and closes, and the keys: the mode field and its
bytes, the hint lines, the prefix sent twice and locked mode reaching the pane
(`--read-bytes`), the four sticky modes, a close that asks, the rename and
command prompts, modes held per client, INPUT and PASTE dropped outside normal
and locked mode, and the key list drawn for one client and closed back to the
exact frame; line one at 20, 80 and 200 columns and with nine tabs at 40, the
zoom mark, the activity and bell marks, the clock and its minute, and (with
/proc) the threads and resident size a pane. The client rows drive the same
split end to end through the real client. The key table itself is held by `src/keys_test.lu` (every binding's
step, the hint lines at 80 and 40 columns, the key list, the command line),
natively, on the checked machine and under lupin. Differences from tmux, by ruling:
warren's split gives the first pane the smaller half (39 and 40 columns at 80,
where tmux gives 40 and 39), and a pane under its minimum is hidden where tmux
keeps 1-row panes.
