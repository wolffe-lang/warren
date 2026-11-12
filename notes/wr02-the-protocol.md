# Protocol v1 prediction

Written before implementation. The starting tree is `7f4f3380`. The codec is
pure: no descriptor, terminal, process or clock is opened by its rows.

## Prediction

The six-byte transport header remains: payload length u32, type u8, flags
u8. Strings cost 2+n bytes; byte strings 4+n; lists 2+items, except
FRAME's u32 run count. All integers are little-endian. The client types
and minimum payload costs are HELLO 27 plus string/environment contents,
KEY 6, MOUSE 7, PASTE 4+n, FOCUS 1,
RESIZE 4, INPUT 4+n, ACK 4, REDRAW 0, DETACH 0, COMMAND 10 plus contents,
and PING 4. Server types are WELCOME 14 plus its two strings, REFUSE
4+text, FRAME 22 plus runs, BELL 0, CLIPBOARD 4+n, TITLE 2+n, BYE
4+text, REPLY 13+out+err, and PONG 4. Every transport frame adds six.
HELLO's fixed-cost count includes its three empty strings and empty env list;
WELCOME includes its two empty strings; COMMAND includes its empty argv
count and two empty strings.

The corrected FRAME represents a run by row, column, rendition, covered
columns, and cell-record count (18 bytes), followed by records of width u8,
repeat u16, scalar count u8 and one to three u32 scalars. Width comes from
the server, not the client's Unicode tables. A wide record consumes two
columns per repetition; continuation cells are implicit and cannot be split.
Equal cells compress by repetition; damage is represented by omitted spans.

Predicted full repaint costs, including one transport header and the
22-byte corrected FRAME prefix (the draft prefix is 20):

| Content | 80x24 draft | 80x24 corrected | 320x90 draft | 320x90 corrected | Transport frames |
|---|---:|---:|---:|---:|---:|
| blank, one run/row | 482 | 652 | 1736 | 2368 | 1 |
| distinct ASCII, same rendition per row | 2378 | 15820 | 30446 | 232048 | 1 |
| distinct ASCII and rendition per cell | 36506 | 49948 | 547226 | 748828 | 1 |
| three four-byte scalars and distinct rendition per cell | 57626 | 65308 | 864026 | 979228 | 1 |

The draft's last row counts 18 bytes plus 12 text bytes per cell. Its lack
of segmentation and explicit widths is not a free compression win: two
clients can otherwise disagree about the cells those bytes mean. The
corrected blank screen stays below a 4096-byte socket buffer; ordinary
uncompressed screens do not. A transport frame never implies one write.

Expected rows: a golden for every message type, fixed HELLO prefix, exact
round trips, every truncation, unknown types, reserved bits, scalar and
colour ranges, invalid UTF-8, all count/length caps, row-major non-overlap,
full coverage, wide-boundary refusal, fragmentation at every short split,
partial-write scheduling in a pure model, stale ACK after image reset,
malformed seeded inputs, and repaint byte counts. The bounded fuzz row is
not a soak and runs on Linux; short deterministic cases run on every tier.
Rows must be committed red before the implementation they test.

## Order

1. State every byte and every refusal in `docs/PROTOCOL.md`.
2. Commit codec rows while `src/proto` remains a stub; record their red.
3. Implement bounded framing, payload validation and canonical encoding.
4. Specify the event loop and its actual standard-library blockers in
   `docs/SERVER.md`; model small state transitions without I/O.
5. Draft the one-pane implementation contract, including Linux, macOS and
   PAX session/terminal-restoration rows, then plant a decoder regression.

## Corrections to the draft

The connection's sequence numbers must never be reused, even after an image
reset, so an old ACK cannot acknowledge a new frame. A base of zero resets
the image only. Before u32 would wrap, reconnect. FRAME cell records make
server-authoritative width and scalar boundaries explicit. FRAME uses a u32
run count so more than 65,535 distinct renditions are representable. Grid
area is at most 262,144 cells. The worst legal repaint payload is 8,912,918
bytes (262,144 runs of 34 bytes plus 22), so its logical cap is 16 MiB, the
smallest power of two that holds it. REPLY is capped at 8 MiB and paste
contents at 64 KiB; a physical payload stays at most 1 MiB. The full
specification will enumerate every remaining ambiguity and its resolution.

## Evidence boundary

The event-loop document is a contract, not an implemented server. At
wolf-std `be1d10fa`, a mixed file/socket waiter, socket write readiness and
socket-plus-signal waits remain named `unsupported`; a nonblocking partial
socket write remains a contract rather than an API. No socket, pty or
process row is claimed by this lane.
