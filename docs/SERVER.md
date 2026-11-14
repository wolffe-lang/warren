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
| sessions | 16 (one pane each in this version) | REFUSE resource-limit (7) |
| connections, every phase | 32 | the listener leaves the readiness set; dials wait in the backlog |
| connections before HELLO | 4 | the same |
| history per pane | 8 MiB | the oldest lines go |
| projected memory | 512 MiB | REFUSE resource-limit (7) |

The projection counts each session's pane (its history, both screens at its
size, 1 MiB of fixed buffers) and each connection (one physical frame's
receive buffer, a paste assembly, the 256 KiB event queue, and, when
attached, one worst-case image and a 64-byte-a-cell shadow of what its
client holds). These counts are revisited when one session holds many
panes.

**On PAX**, a server takes three of the machine's 64 thread slots (its main
thread and two the runtime starts for signals and children; measured under
QEMU), and every wolf program inside a pane takes two (pax#354 is the
machine-wide limit). A Unix stream holds 4096 bytes in each direction, so a
repaint always spans several writes. Surviving a console logout depends on
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
| running | close binding/command | unregister, close master; retain child in reap registry; start 3 s deadline | closing |
| closing | child reaped or 3 s passed | remove visible pane; retain unreaped child in registry until eventual exit/server end | gone |
| exited | remaining output consumed | remove pane; empty tab closes; empty session ends; keep unreaped child tracked | gone |
| dead | key acknowledging failure | remove error pane; empty-session rules apply | gone |
| gone | late child exit | reap through retained registry, no owner resurrection | gone |

The draft's child-exit and master-end ordering must not cause a second
blocking read: after a read reports eof/io, it is ended. On Linux a master
whose slaves closed commonly reports `io` (EIO), on macOS `eof`; the next
implementation's host rows must assert this explicitly. Fatal read errors
also remove that master and surface an error, never busy-spin on READ.
A vanished pane may still have a child to reap: layout ownership and process
ownership end at different times. Closing the master is the only way the
server asks a program to end; the server never sends it a signal. In
particular Ctrl-C is input byte 03 to the pty, not a signal API call. A child
that ignores hangup can outlive pane removal; show/report this limitation,
never silently add a kill fallback.

Start with `term.open_pty`, `process.command`, argument/environment setup,
`process.set_stdin`, `set_stdout`, `set_stderr`, and
`process.start_session` with the pty slave. Startup must reset signal
ignore/blocked state and inherit no unrelated masters or sockets; this is
an end-to-end row, not inferred from the function name. Reap using
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

The transitions are exercised through the real event dispatcher by the
session rows (`src/session_rows.lu`): a scripted client, itself wolf so that
PAX runs it too, drives a real server over its socket. Each row starts its own
server in its own runtime directory with a lifetime bound and stops it with
`kill-server`. They cover HELLO split at every byte, a bad first frame and bad
magic (closed silently), the version, no-session and read-only refusals, a
too-small attach (WELCOME then BYE, no session created), the HELLO deadline,
stale and future ACKs, a message inside a paste's fragment chain, two client
sizes converging to their minima and back, a client that never ACKs beside an
active one, detach by the prefix binding and by DETACH, Ctrl-C as the byte 03,
the last session ending the server, the command role, and a second server
meeting the start lock. `src/compose_rows.lu` holds every composed image,
applied by the client's applier, to the emulator's stored cells.

This version answers a command connection's COMMAND for `kill-server` and
`list-sessions` only; every other verb replies status 2 and names itself as
not implemented. A pane whose program does not start is refused (REFUSE
invalid-request, with the reason) rather than shown as an error pane.
