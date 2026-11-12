# Next lane: one pane, detach and attach

## Goal and base

Implement W2 from the protocol lane's gauntlet-green head, after the emulator
lane's agreed public screen API is available. The work is server, client and
one pane, not splits/tabs/configuration/scrollback UI. Read README, MAP,
PROTOCOL, SERVER, SCREEN-DUMP and TERM in full, the emulator API document and
its rows, then the standard-library docs/tests at the actual toolchain pin.
The protocol lane's note is a prediction, not a claim that any socket or pty
has been opened. Preserve the clean room: never another multiplexer's,
terminal emulator's, terminal library's or kernel's source. Documents and
black-box binaries are allowed; no online implementation/protocol searches.

## Blocking dependencies, before implementation

1. Pin a released wolf/standard-library pair serving ONE mixed file/socket/
   signal wait, all ready entries and READ/WRITE, with a deadline. At
   wolf-std be1d10fa this is still `unsupported`. Read its sc82 note, M1;
   the existence of `std.poll.Waiter` alone is not completion.
2. Require a real nonblocking partial socket write (`net.write_some`, M2),
   not whole-write-plus-readiness. Prove it returns a prefix/count or busy
   with a peer that stops reading and a 4096-byte buffer model, before the
   first server loop.
3. Verify an atomic startup lock or atomic exclusive create. Refuse unsafe
   stale-path replacement; do not improvise exists-then-create.
4. Verify peer-credential availability (M3); where unavailable document the
   0700 directory boundary and test another uid cannot traverse it.
5. Verify PAX's persistent pid 1, logout/reaping and runtime-directory work
   before promising a server survives console logout. Keep that promise
   separate from merely surviving the client process.
6. Consume the emulator's public cells/answers/events/resize contract.
   Do not edit or independently reimplement `src/vt` or its Unicode widths.

If 1 or 2 remains missing, hand back with exact calls/refusals and a proposed
dependency, not a busy-poll loop, helper process or background thread.

## Prediction and memory budget first

Commit a prediction before code. At 80x24 and 320x90 predict compose/encode/
apply costs, changed-cell vs full-frame bytes and latency, one-client and
two-client memory, and maximum resident memory on the 2 GiB target. Distinguish
byte buffers from object/list overhead. Budget admission across connections,
panes, grids, histories and outstanding images; per-message caps alone do not
bound a server accepting arbitrary peers. The protocol cap is 262,144 cells,
FRAME 16 MiB, REPLY 8 MiB, paste 64 KiB, event output 256 KiB per attached
client. A peer with no ACK retains one image only. Request explicit approval
before selecting user-visible connection/pane limits or reducing these caps.

## Items, with red rows before each behavior

1. **Transport.** Bounded receive assembly and partial-send queues over Unix
   streams. Negotiate the permanent HELLO prefix before interpreting its
   versioned suffix. Use the pure codec and preserve exact no-resync/error
   behavior. Every protocol message/fragment may split at every byte. A
   stalled peer and a 4096-byte stream never park the event loop. A large
   logical FRAME must exercise multiple physical fragments and loop turns.
2. **Server core.** One per user; secure runtime directory/start lock;
   bounded accept; own detached session; one pty master and one session child
   with clean signals and intended descriptors only. One readiness set over
   listener, sockets, masters, signals and nearest monotonic deadline. Honor
   the ownership, read budgets and transitions in SERVER. Keep zombie reaping
   independent from visible pane removal. Never signal a pane program: close
   its master; Ctrl-C is byte 03.
3. **Compositor.** One emulator grid to one protocol image; no bars beyond a
   minimal status/error line needed by the one-pane contract. Compare compose,
   encode, decode, apply against the emulator's stored cells, including marks,
   explicit widths, continuations, attributes and cursor. Include old and new
   halves in damage when overwriting a wide pair. One image outstanding;
   damage accumulates, not queued images. RESIZE/REDRAW force a full image
   after ACK but never reset connection seq. Wrap causes reconnect, not reuse.
4. **Client.** Save termios before raw; restore on every catchable exit path.
   Render from explicit server widths, never infer Unicode width. Implement
   keys/mouse/paste/focus/resize parsing and mode-aware routing needed by the
   one-pane tests. Prefix/detach binding belongs to the server. Use outer
   terminal capabilities without changing the inner TERM promise. PAX draws
   one cell per code point and sixteen colours: place wide glyphs explicitly,
   omit unsupported combining glyphs without moving subsequent cells, and
   downsample colours. Never send DCS/APC strings to PAX's console. Use a
   documented renderer policy with rows rather than probing unanswered
   queries indefinitely. Request decisions for visible fallbacks.
5. **Session lifecycle.** `warren` default create-or-attach, explicit new and
   attach, detach binding, reconnect, second client, smallest-client sizing,
   no clients keeps last size. Too-small clients are WELCOME/BYE, not retained
   participants. Client loss never closes its pane or its other clients.
   Session end and server shutdown follow the bounded drain tables.
6. **CLI and docs.** Replace the executable scaffold with actual W2 verbs;
   unimplemented future verbs fail by name. Refresh README/MAP, document the
   implemented scope and divergence/limitation table. Do not claim W3 keys,
   layouts, configuration or persistence are complete.

## Rows and hosts

- Pure codec/model rows on native Linux/macOS, checked (`conform-run --json
  --checked`, not `run --checked`) and lupin where supported. No silent
  native fallback. A named unsupported tier is not a pass.
- Integration socketpair/scripted peers traverse every connection transition,
  malformed header/payload, role violation, HELLO timeout, fragment interleave,
  drain timeout, stale/future ACK, old-size image crossing RESIZE, partial
  write and stalled reader. Include a never-ACK client beside an active one.
- Own-pty session rows: a shell echoes a line, detach/attach preserves it;
  two client sizes converge to the minima; a hot pane cannot starve a key or
  deadline; closing one client leaves both pane and second client alive.
- Own-child rows: inherited ignored/blocked signals are reset; Ctrl-C written
  as pty byte 03 ends the foreground command, not server; child-exit before
  master-EOF and the reverse preserve final output; late exit after pane
  removal is reaped; no helper/thread is created by the event loop.
- Terminal rows read back saved termios and outer-emulator modes after BYE
  each code, REFUSE, server EOF, malformed image, socket/tty write failure,
  catchable terminate, suspend/continue and setup failure. SIGKILL cannot run
  cleanup and must be reported as such, not promised restored. Compare
  behavior with tmux as a pinned black box only where equivalent.
- Linux runs the pinned oracle container under a memory cap and CPU locks;
  macOS correctness behind the directory build lock, no fuzz soak. Build
  from committed snapshots, at most two local workers, disk/memory floors.
- **PAX under QEMU:** build static Linux binaries at the same pin; one pane
  at console and over burrow, detach/attach/second client, nested resize,
  raw restoration, signal keys as pty bytes, smallest-size repaint, stale
  socket/start race, client flood/backpressure, shell startup and logout
  survival. Readiness and partial socket writes must actually execute there,
  not be skipped by platform tests. Measure process/thread-slot use. No real
  hardware until the QEMU half passes and the separate hardware permission
  exists. Never inspect kernel implementation to explain a failed row.

## Delivery and size

Expected 3 coherent PRs, approximately 10–15 implementation days total:
transport/event loop 3–4 days; compositor/client/terminal cleanup 4–6;
lifecycle and Linux/macOS/PAX end-to-end coverage 3–5. The runtime dependencies
and emulator API can add calendar time, not excuse unmeasured claims. Each
PR has its own exact-head record, prediction scored, named local plant and
small narrative commits. Prefer intermediate green PRs to a single large
patch. This estimate is scope planning, not a performance measurement.

Push only the assigned lane and one-hunk plant branches, never trunk. No
merging, labels, issues, releases or attribution trailers. Plants are pushed
without PRs. Read CI status once immediately after push, record ids, do not
wait. The final PR has Forbidden, Inputs verified, Prediction, Evidence index,
Done-when and a Footprint line. Hand back exact heads, every record's path/
SHA-256/END lines, plant branch and named red row, prediction vs measurement,
open limitations, decisions requiring approval and the next scoped contract.
A job detached beyond twenty minutes is handed back with pid, log and exit
marker rather than silently watched forever.
