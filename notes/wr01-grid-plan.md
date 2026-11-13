# Grid slice directive

This follow-on preserves the initial grid work begun from parser head
`d966f49` and now runs on `wr01-grid` from merged parser trunk `2bb72fab`.
It is not a claim that the remaining W1 gates have passed.

## Prediction before code

1. Add the pure pane and screen shapes in `src/vt/grid.lu`. A screen uses a
   flat cell array plus per-row extents and wrap flags; each cell holds a base,
   two combining marks, width, rendition flags, foreground and background.
   Colours retain their set form: default, palette index, or tagged RGB.
2. Commit a constructor seam and failing rectangular-grid rows first. Expect
   the empty-array seam to fail `grid-rectangular`; then allocate independent
   primary and alternate screens, blank cells, default tabs and the whole
   scroll region. The one-row case must use region `1–1`.
3. Add printing and C0 rows red first: deferred wrap, CR/BS/LF/HT, scrolling a
   one-row screen and extent changes. Only ASCII is claimed at this step;
   the width table, pair repair and combining marks follow explicitly.
4. Add cursor/erase and rendition rows, then modes and saved cursor, followed
   by the alternate screen. Run the eight full oracle cases once the dump
   boundary exists; until then the rows inspect screen state directly.
5. Complete widths, resize/reflow and history only with their invariant and
   resource rows. No Unicode approximation is presented as the final table.

The provisional 64-byte-cell prediction in the main note remains the budget.
The initial seven-integer cell is 56 bytes of native scalar payload before
container overhead. At 80×24 the two screens should therefore be near 220 KiB,
not including parser state or history; the implementation's ledger, not this
arithmetic, supplies the measurement.

## Continuation order

The constructor, ASCII/C0, cursor/erase, rendition, narrow editing, bounded
final-state events and deterministic dump have native/interpreter rows.
The generated Unicode 15.1 decision tree and initial Unicode printing/pair
repairs now have positive native/interpreter rows after committed red rows.
The assigned-scalar xterm sweep is still pending: neither the normative
properties nor three locale identity samples stand in for it.

Next, complete the remaining operation/mode/answer dispatch with red-first
rows, then integrate fixed-byte history and capacity-reusing resize/reflow.
The adopted draft records the peak-capacity allocation model, off-viewport
cursor projection/commit rule, and 24-byte history header. Its property rows
must be implemented before claiming those policies work. Preserve content
and rendition in the one-column wide exception and restore natural width
on widening; no resize implementation exists yet.

The next allocation step first tests private capacity growth independently
of resize: logical dimensions and visible cell values stay unchanged, backing
cell/row/tab lengths grow geometrically and never shrink, and repeated
small/large reservations must plateau on native and lupin. The area check
uses division before multiplication and refuses rectangles above 262144
cells, including integer-overflow inputs. This groundwork is not a resize
or history claim. Reflow later adds reusable source/output workspaces and
must include their actual peak charges in the ledger.

The history groundwork next tests the fixed-byte framed ring independently
of screen encoding: 24-byte LE headers, whole-record eviction, constant-time
oldest removal, reverse traversal through previous lengths across wrap,
and no per-append allocation. A record that cannot fit even in an empty ring
must discard the older prefix and itself, not keep stale older text after a
missing newer record. Screen-line encoding, stable IDs through reflow and
history feed integration remain separate rows; a ring-only pass proves none
of those. The first implementation uses no unbounded line index.

## Line-encoding continuation

After framing, encode screen content directly into a reserved ring record in
two bounded passes: count exact bytes/runs, reserve/evict whole records, then
write. No temporary per-line List or growing index is needed. Continuation
cells are not text; base plus at most two marks is UTF-8. A 12-byte run is
three LE u32 words: text-byte count, foreground/control, background/control.
The low 26 bits of each colour word encode default=0, palette=1+index, or
RGB=(1<<25)+RGB24. Foreground bits 26..31 hold rendition bits 0..5;
background bits 26..28 hold rendition bits 6..8, with bits 29..31 naming a
run kind (ordinary content=0, unwritten background paint=1; others unused).
Unused bits are zero. This keeps all nine flags and the original colour
form without allocating a style dictionary.

Keep background paint past the extent separate from logical content. Its
positions must be reconstructible, including default-colour gaps before a
nondefault background; paint never creates additional logical text or rows.
A reusable scalar reader walks run headers/UTF-8 and exposes scalar fields,
not newly allocated records. Its storage is separate from the ring so that
adding reader fields cannot silently change the measured ring overhead.
Rows must cover round-trip colours/flags/base/two marks, content versus
paint, exact encoded byte counts, and flat repeated encode/read charge.
This is still groundwork: feed/history integration, 65536-cell splitting,
stable-ID assignment and the path-independent reflow source remain pending.

## Feed integration continuation

Framing, run encoding/reading and bounded fragment/counter rows now exist;
none is wired into Vt yet. The next coherent step adds row metadata for a
stable logical-line ID and start offset, plus a primary-screen monotonic ID
allocator. A physical row may produce one or more encoded fragments;
fragments need not be maximal, and no fragment boundary is a logical newline.
This permits appending the row leaving the top directly, without rewriting
an open record or keeping a per-line index. A reusable LineCoordinate value
avoids returning allocated records during feed. Initial/blanked rows get
fresh IDs; copying rows copies their addresses; RIS must not recycle lifetime
IDs. Wraps join IDs and advance offsets by natural glyph widths, including
the one-column wide exception. Structural breaks/line edits must repair
joined-row addresses to agree with wrapped edges, rather than leaving stale
same-ID suffixes behind a newly inserted hard line.

A row can cross the 2^32 coordinate boundary at most once under the area cap.
If its continuation ID is reserved before that row leaves the screen, keep
that one overflow ID in bounded row metadata so later encoding reuses it;
it must not allocate a second identity for the same suffix. Feed integration
must cover history only for primary upward removal with region top 1,
including SU, never the alternate screen or a lower region; ED3/RIS empty
history without changing the screen incorrectly. Disabled history should
have a fast path while still reporting prefix loss to resize bookkeeping.

Once Vt actually allocates its configured history, change generic screen-only
constructor rows to cap zero and ownership rows to a small configured cap.
Keep default-8MiB pane/ring rows native-only; interpreter entries explicitly
configure a smaller ring under the unchanged cap, as the ledger finding
requires. This is a tiered test configuration, not a hidden skip or an
increased interpreter budget. Resize/reflow and its canonical resize-only
source remain the major step after feed integration.

One standalone read-only host preflight has passed. Prepare the complete
host take before acquiring a pool slot; no heavy work is assigned to the
other pool host. The first grid review leaves this exact Done-when row open:

> PAX corpus leg: not run, no boot fixture in this repository yet
