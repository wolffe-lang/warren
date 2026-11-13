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

One standalone read-only host preflight has passed. Prepare the complete
host take before acquiring a pool slot; no heavy work is assigned to the
other pool host. The first grid review leaves this exact Done-when row open:

> PAX corpus leg: not run, no boot fixture in this repository yet
