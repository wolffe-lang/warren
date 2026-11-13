# Wire protocol v1

This is the byte contract for a second implementation. It describes a local
Unix-domain stream, not a terminal dialect. The server owns ptys and screens;
clients own drawing and their terminals. No descriptor is transferred. The
pure `src/proto` codec does no I/O. SERVER.md specifies connection state.

## 1. Transport and version

All integers are unsigned little-endian. A physical frame is `length u32,
type u8, flags u8, payload[length]`. Length excludes the six-byte header and
is at most 1,048,576. Flag bit 0 is MORE; every other bit is reserved zero.
Only FRAME, PASTE and REPLY permit MORE. Consecutive fragments of one logical
message have the same type; MORE is set on all except the last. Fragment
payloads are concatenated raw, then decoded ONCE. A fragment is not an
independent payload encoding. No other message may interrupt that chain,
including PING or BYE; aborting it requires closing the connection. Empty
MORE fragments are invalid. A single final empty fragment is allowed.

The receiver checks the header before buffering its payload, and checks the
aggregate cap before appending each fragment. Caps include payload prefixes:
FRAME 16 MiB; REPLY 8 MiB; PASTE 65,540 bytes (a u32 count and at most 65,536
content bytes); every other message 1 MiB. A complete physical frame is
consumed at a time. EOF inside a header, body or fragment chain is a truncated
connection, never a partial application. Socket reads may contain any part
of any number of frames; bytes after a complete frame belong to the next.
There is no resynchronization after an invalid frame.

Strings (`str`) are u16 byte length then strict UTF-8: no overlongs,
surrogates, incomplete sequences or values above U+10FFFF. No normalization.
Byte strings (`bytes`) are u32 length then uninterpreted bytes. Lists use
u16 count, except FRAME's u32 run count. Each count must fit the remaining
payload before the decoder allocates/iterates its items. All payloads must
be consumed exactly; trailing bytes are an error. Text is data, not trusted
escape sequences: terminal renderers sanitize TITLE and clipboard controls.

The first frame is client HELLO, unfragmented. Its first eight payload bytes
are permanently fixed, including across future versions: `57 52 4e 00`
(`WRN\0`), `proto_min u16`, `proto_max u16`. Require min <= max. The server
chooses the highest common version (v1 here). If there is none it sends
REFUSE code 1 using v1's `code u16, text str`, then drains/closes without
interpreting the version-dependent HELLO suffix. Bad magic or a non-HELLO
first frame closes silently. Future versions must preserve this bootstrap
header, HELLO prefix and version-REFUSE encoding. After choosing v1 the whole
HELLO is validated by v1 rules. WELCOME's version is 1. The version changes
if a field, meaning, cap, enum or compatibility promise changes; unknown
message types, enum values or bits are errors, not extensions to skip.

## 2. Client messages

Payloads below do not include the physical header. A list of pairs has one
list count followed by each first/second string, not nested pair counts.

| Type | Name | Payload in byte order | Minimum bytes |
|---|---|---|---:|
| 01 | HELLO | magic[4], min u16, max u16, role u8, cols u16, rows u16, depth u8, features u32, term str, target str, options u8, cwd str, env list<pair<str,str>> | 27 |
| 02 | KEY | mods u8, kind u8, code u32 | 6 |
| 03 | MOUSE | kind u8, button u8, mods u8, col u16, row u16 | 7 |
| 04 | PASTE | bytes | 4 |
| 05 | FOCUS | gained u8 | 1 |
| 06 | RESIZE | cols u16, rows u16 | 4 |
| 07 | INPUT | bytes | 4 |
| 08 | ACK | seq u32 | 4 |
| 09 | REDRAW | empty | 0 |
| 0a | DETACH | empty | 0 |
| 0b | COMMAND | id u32, argv list<str>, cwd str, pane str | 10 |
| 0c | PING | nonce u32 | 4 |

HELLO role is 1 attach or 2 command. Depth is 0 no colour, 1 sixteen,
2 indexed 256, 3 RGB. Features bits: 0 bracketed paste, 1 focus, 2 SGR
mouse, 3 OSC 52 writes, 4 cursor shape; other bits zero. These describe the
outer terminal and gate client behavior, not emulator features promised to
programs inside. Options bit 0 creates the missing session; bit 1 asks for
read-only attach (well-formed, but REFUSE code 3 in v1); others zero. Target
empty means default. Attach dimensions are nonzero and area <=262,144;
command dimensions may both be zero (otherwise the same bound). RESIZE
always uses the nonzero bound. The usable minimum is 20x6: a smaller attach
gets WELCOME then BYE code 7, and never participates in session sizing; a
resize below minimum detaches with BYE 7. No process is created for an
initial too-small attach. The working directory and environment are used
only to create a session; they never change an existing session's environment.
An env name must be nonempty, contain neither NUL nor `=`; env values, cwd,
term, target, argv and pane must have no NUL. Duplicate env names are
invalid; the decoder's linear scan does not compare all names, so that
policy is enforced by the server's bounded environment map, before creation.

Mods are shift=1, alt=2, ctrl=4, combinations permitted. KEY kind 0 is a
Unicode scalar (including NUL, with control policy on the server); kind 1
is a named key: 1 Up, 2 Down, 3 Right, 4 Left, 5 Home, 6 End, 7 PageUp,
8 PageDown, 9 Insert, 10 Delete, 11 Backspace, 12 Tab, 13 Enter, 14 Escape,
15..38 F1..F24, 39 keypad0, 40..48 keypad1..keypad9, 49 keypadDecimal,
50 keypadDivide, 51 keypadMultiply, 52 keypadSubtract, 53 keypadAdd,
54 keypadEnter, 55 keypadEqual. MOUSE kind is 0 press, 1 release, 2 motion,
3 wheel-up, 4 wheel-down; button 0 none, 1 left, 2 middle, 3 right. Wheel
requires button 0; press/release require 1..3; motion permits 0..3.
Coordinates are nonzero, 1-based in the client's current composed frame;
the server discards a well-formed event outside the current image. FOCUS is
0 or 1. ACK is nonzero. COMMAND id is nonzero; empty argv is invalid.
INPUT is at most 65,536 content bytes. PASTE contains at most 65,536 bytes;
its entire logical message is delivered to the selected pane or dropped.

Input events from one client are applied in wire order. Between clients,
server read order is the only promise. The server owns bindings, prefix,
focus and modes. It encodes KEY/MOUSE for the pane's requested dialect, not
the outer terminal's. INPUT passes unchanged in normal/locked mode and is
dropped in other modes. Paste sanitization removes every `ESC [ 2 0 1 ~`
sequence (even across transport fragment boundaries); without bracketed
paste, remove control bytes 00..1f and 7f except tab, CR and LF. UTF-8 bytes
above 7f are not stripped. Admit the sanitized paste plus any bracket bytes
to the 64 KiB pane queue atomically or drop it all, with a visible overflow
indicator. Other input is dropped when it cannot fit, never blocking a loop.

## 3. Server messages

| Type | Name | Payload in byte order | Minimum bytes |
|---|---|---|---:|
| 81 | WELCOME | proto u16, client u32, server_pid u32, session str, server_version str | 14 |
| 82 | REFUSE | code u16, text str | 4 |
| 83 | FRAME | section 4 | 22 |
| 84 | BELL | empty | 0 |
| 85 | CLIPBOARD | bytes (at most 65,536 content bytes) | 4 |
| 86 | TITLE | text str | 2 |
| 87 | BYE | code u16, text str | 4 |
| 88 | REPLY | id u32, status u8, out bytes, err bytes | 13 |
| 89 | PONG | nonce u32 | 4 |

REFUSE codes: 1 version, 2 no-session, 3 read-only, 4 permission, 5 busy,
6 invalid-request, 7 resource-limit. BYE codes: 1 detached, 2 session-ended,
3 server-stopping, 4 replaced, 5 too-slow, 6 protocol-error, 7 too-small.
WELCOME client is nonzero; session is empty for command role. REPLY id is
nonzero and matches COMMAND; status 0 successful, 1 refused, 2 usage,
3 no-server. Output/error are bytes, not necessarily UTF-8. REFUSE and BYE
are terminal: close after draining or after two seconds. Error text is
explanatory, never parsed as a code. A malformed message after bootstrap
gets BYE protocol-error if it can be appended without corrupting a partial
frame/fragment chain; otherwise close immediately. Queued writes are never
rewound or interleaved to insert an error. WELCOME precedes other ordinary
server messages. Role command accepts one COMMAND then replies and closes;
it never receives FRAME. Role attach never sends COMMAND. PING/PONG are
permitted only after WELCOME and before draining, outside fragment chains.

## 4. FRAME and image rules

```
seq u32, base u32, cols u16, rows u16
cursor_row u16, cursor_col u16, shape u8, visible u8
run_count u32
repeat run_count times:
  row u16, col u16, rendition_flags u16, fg u32, bg u32
  columns u16, record_count u16
  repeat record_count times:
    width u8, repeat u16, scalar_count u8
    scalars[scalar_count] u32
```

Seq is nonzero. Base is 0 or seq-1. Dimensions are nonzero, area <=262,144.
Cursor is in bounds even when hidden; shape is DECSCUSR 0..6, visible 0/1.
A colour is exactly 00000000 default, 01000000|index (0..255), or
02000000|R<<16|G<<8|B (all bytes 0..255). Other encodings are invalid.
Rendition flags, low to high: bold, dim, italic, underline, double-underline,
blink, inverse, invisible, strike; remaining bits zero. Underline and double
underline cannot both be set. This is the original draft's rendition set;
any later emulator decoration not in it needs a separately versioned wire
extension rather than silently taking reserved bits.

A cell record has width 1 or 2, nonzero repeat and scalar_count 1..3.
Scalars are Unicode scalars; no width/grapheme computation is done by the
client or codec. The emulator is the single width authority. The first
scalar is its base, the remaining at most two are its stored marks. Scalar
sequence structure is the server's responsibility; scalar validity is the
codec's. Each repetition occupies width columns and generates an implicit
continuation for width 2. A run covers exactly the sum of these products,
never wraps across a row, and has at least one record. The run's rendition
applies to every leading and continuation cell. Equal cells may use repeat;
unchanged spans are omitted from a delta. Runs are in row-major order,
nonoverlapping, and no two runs may share a column. A full image (base=0)
covers every cell exactly; a delta may have zero runs (cursor-only). Run
count <= area, record count <= columns, with checks before iteration.

**M1. Connection-unique numbering.** Sequence numbers strictly increase
without reuse within a connection, including after RESIZE, REDRAW and
session switch. First seq is 1. Before u32 wraps, reconnect; never send 0.
Base=0 resets the image, not the numbering. A stale ACK therefore cannot
name a live frame: only the exact outstanding seq may release it. An ACK
<= last acknowledged seq is ignored; a future or never-sent ACK is a
protocol error. The pure acknowledgement model has a stale-after-reset row.

**M2. One outstanding image.** The server sends no next FRAME until the
current FRAME is fully transmitted and ACKed. ACK means the client decoded,
applied AND drew the whole logical FRAME. It must not ACK a transport
fragment. The sender keeps only one immutable encoded image pending; new
damage is accumulated in the current screen, not as queued images. After
ACK, compose the latest damage relative to that acknowledged image. A
RESIZE/REDRAW during an outstanding image sets force-full; finish/ACK the old
one before sending the next base=0 image with the next seq. A client must
continue consuming/ACKing old-size images while its request crosses them.
This preserves bounded memory and removes races between duplex streams.

**M3. Wide-safe application.** A full image cannot split a wide record by
construction. For a delta, in addition to local decoding, the image applier
must check the existing image: no changed span may leave an old wide pair's
leading or continuation half untouched. Include both columns, even if one
becomes a blank. Refuse and close on a state-dependent violation; neither
the stateless decoder nor the renderer guesses at an orphan. Damage must
include both halves of old and new wide pairs. Apply only to an existing
image whose seq equals base; base=0 replaces it. The model application row
must compare all scalars, widths, renditions and cursor, not rendered bytes.

**M4. Repaint bounds.** At 262,144 cells, each having three scalars and its
own rendition/run, payload is 8,912,918 bytes. FRAME's 16 MiB cap is the
smallest power of two holding it. Prefix is 22 bytes; a run costs 18 plus
8 bytes for a one-scalar record or 16 for three. A blank 80x24 repaint costs
652 wire bytes; 320x90 costs 2368, using one repeated blank record per row.
Distinct ASCII cells with one rendition per row cost 15,820 and 232,048;
with a rendition per cell cost 49,948 and 748,828. Three four-byte scalars
per cell and distinct renditions cost 65,308 and 979,228. All these examples
use one physical frame. A maximal payload needs nine, totaling 8,912,972
wire bytes. No encoder relies on a socket buffer holding any whole image.

## 5. Stream flow and boundedness

Each connection has one inbound physical buffer (six-byte header then at
most 1 MiB body), at most one logical assembly, and an outbound byte queue
with an offset into its current physical frame. Parse/validate lengths before
copying. A frame body is only retained after header bounds pass; a fragment
is only appended after aggregate bounds pass. Do not repeatedly concatenate
or re-decode a growing assembly: append to one amortized list and decode
once. Time and memory are linear in bytes consumed, with bounded metadata.
An implementation may return a named limit refusal before allocating.

All descriptors are nonblocking; socket writers need a one-send partial
write primitive. Advance the offset only by the reported count, keep the
suffix on busy, request WRITE only while queued, and never queue the same
bytes twice. A 4096-byte socket is ordinary. Read, write and parse at most
64 KiB per handle per turn; an already-buffered complete message schedules
another immediate turn rather than waiting for a new kernel edge. Large
messages span turns. Non-FRAME outbound data is capped at 256 KiB per attach
client; command REPLY uses one bounded message, not that attach-event queue.
Exceeding the event queue detaches only that client (BYE too-slow if safe,
else close). One unacknowledged FRAME has no timeout in v1; it cannot prevent
pty draining or another client progressing. No peer can make a blocking
write or an unbounded allocation. Connection count and global memory limits
are server admission policy; the next implementation contract must budget
them on the target machine before accepting clients.

## 6. Changes from the draft

1. Sequence reuse after resize/redraw is removed. Monotonic connection-wide
   seq and base=0 image resets prevent an in-flight old ACK 1 releasing a new
   image 1. Outstanding old images drain/ACK before a forced full image.
2. Unsegmented grapheme text becomes explicit width/scalar/repeat records.
   Client Unicode tables otherwise disagree about cell boundaries; the wire
   can neither validate coverage nor stop wide splitting. There is no
   continuation record that could be orphaned. The byte cost is above and
   in the prediction table; repetition/omitted spans preserve compression.
3. FRAME run count is u32, prefix 22 rather than 20 bytes. A legal large
   screen can need more than 65,535 runs with distinct renditions.
4. Caps are fixed: area 262,144; FRAME 16 MiB, REPLY 8 MiB, PASTE 64 KiB
   contents. The worst legal FRAME exceeds 8 MiB, requiring 16. The draft
   capped physical frames only and otherwise permitted unbounded assembly.
5. Fragmentation is raw concatenation, single type, no interleaving, length
   checked before append, then one payload decode. This removes ambiguity
   about repeated prefixes and avoids quadratic reassembly.
6. A tiny client gets WELCOME/BYE, as the draft's state table, not the
   survey's attached-but-not-counted proposal. Counting it would shrink all
   other clients; keeping an attached nonparticipant adds a second client
   sizing mode. No too-small initial attach creates a session.
7. Every enum, bit, key number, error code, colour and exact consumption
   rule is enumerated; the draft left their numerical values/reservations
   implicit. FRAME runs are ordered, full coverage required, dimensions and
   scalar counts bounded. These make validation linear without a bitmap
   allocation and remove second-implementer guesses.
8. Delta wide-pair validation is explicitly divided into stateless record
   checks and application against the old image; bytes alone cannot show
   whether a delta touches half of an old pair. Command/attach roles and
   bootstrap refusal ordering are explicit. Terminal title/clipboard text
   must not be replayed as trusted escapes.

9. At one column the server may send a width-1 record whose scalar is naturally wide, and the client clips or substitutes; nowhere else.

No server, client, socket, pty or process is implemented by this document.
