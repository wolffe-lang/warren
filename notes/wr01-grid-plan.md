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

The provisional 64-byte-cell prediction in the main note is now the approved
native cell payload, including a scalar written bit and alignment, measured
and asserted at `7450229` by `cell_capacity_rows.lu`. The former seven-integer
payload was 56 bytes; it could not retain erased gaps for later edits. Current
whole-pane charges and the independent interpreter ledger are measured and
asserted in `pane_capacity_rows.lu` and `pane_ledger_rows.lu`; the table in
`wr01-the-emulator.md` records them. None is an RSS claim.

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

Framing, run encoding/reading and bounded fragment/counter rows now exist.
The constructor allocates Vt's fixed ring and row metadata. Primary scroll
removals are now connected to whole addressed fragments, with native/lupin
rows for regions, alternates, SU, ED3/RIS, lifetime IDs, feed charge and every
split of a mixed line-edit/scroll stream. Natural offsets at one column and
a reserved coordinate-overflow ID have direct rows too. The implementation
uses stable logical-line IDs and start offsets with a primary-screen
monotonic allocator. A physical row may produce one or more encoded fragments;
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

History allocation is now real in Vt. Generic screen-only constructor rows
use cap zero and ownership rows use a small configured cap.
Keep default-8MiB pane/ring rows native-only; interpreter entries explicitly
configure a smaller ring under the unchanged cap, as the ledger finding
requires. This is a tiered test configuration, not a hidden skip or an
increased interpreter budget. Resize/reflow follows as the next section's
original prediction; its implemented checkpoint is recorded below.

## Resize epoch prediction, before code

The proposed pure boundary returns the empty string on success or the static
name `vt-size-area` on an invalid/oversized rectangle; it does not allocate
a result record or mutate state for a refused or same-size request.

- Keep a reusable original-primary snapshot for a resize-only epoch and a
  separate output workspace. Capture cursor and saved-cursor logical anchors
  plus original physical positions. A nonempty feed commits the displayed
  projection and invalidates the epoch; eviction invalidates it too.
- Keep an encoded canonical deque of epoch screen rows and only the history
  suffix brought into the reflow window. Complete the first retained logical
  line before counting its wrap phase; then batch older whole logical lines
  to fill a height deficit, not one fragment/recount at a time. A visible
  logical line may span the retained history cap; unrelated lines are not
  scanned. The snapshot preserves original physical rows whenever the target
  width equals the epoch's original width, including unwritten wide-wrap
  gaps and background paint that canonical text alone cannot reconstruct.
- Track how many leading live-history records still belong to the original
  prefix. Resize-generated prefix copies are a trailing shared portion:
  remove those copies before the next resize, then work from original history
  plus the canonical deque without duplication. Pulling an original record
  decrements the original-prefix count and gives its canonical copy ownership.
  Re-encode/copy the canonical portion before the new viewport into history.
  A cap eviction commits the finished materialized state as a new epoch, so
  no retained snapshot can resurrect an evicted prefix.
- Bound canonical bytes by the configured history cap plus 48 times peak
  cell capacity: at most the original retained history plus the epoch screen
  encoding. Include geometric rounding and abandoned growth buffers in the
  ledger. This is an explicit extra workspace term, not free duplication of
  history. A resize within peak capacity adds no charge. Verify an outer-owned
  pane resized through short-lived turn regions, not only a pane and resize
  born in the same region.
- Reflow in two scalar passes: count/locate the new viewport and anchor maps,
  then fill only its rows. Background-paint runs never become logical content
  or extra rows. A wide glyph moves whole; one-column presentation keeps its
  natural-width address. Preserve the original off-viewport anchor until
  feed or eviction commits a projected position.
- Resize the alternate screen top-left without reflow, repair cut pairs,
  reset the region/default-tab growth and clear pending wrap. Reflow primary
  even while alternate is active; map primary saved cursors independently.

Lane decision for R5: when growing taller, pull older rows while available;
when history is exhausted, existing text remains top-anchored and extra rows
are bottom padding. A fresh shell prompt does not move down merely because
its window grows. The first rows are 4x1 to 4x3 with no older line, exactly
one older line, and more history than the two added rows. These rows now
exist and had an observed geometry assertion before their implementation.

## Implemented resize checkpoint

The pure resize entry and its native/lupin properties now cover R1-R8:
content and direct-versus-intermediate paths, bounded original-history
ownership, logical/saved/projected cursor anchors and feed/eviction commits,
one-column natural widths and unwritten wide-wrap gaps, alternate clipping
and hidden-primary reflow, region/tab resets, incremental CSI/UTF-8, exact
same-size/refused no-ops and repeated outer-owned child-turn capacity reuse.
The original-width path uses snapshot rows for all heights, not just the
original height. A retained first logical line is completed before counting
its wrap phase. TBC-all now clears retained hidden stops; that regression
was observed red before its one-line correction. This is written-property
evidence, not a claim that the full reference corpus or width sweep passed.

Next: CLI/raw and recording replay, complete corpus comparison with named
divergences, the assigned-scalar width sweep, first-divergent-prefix tooling,
resource/performance and plants, then the single prepared host take and PR.

## Dump/replay boundary prediction

Add the host-side `warren vt-dump [--cols N --rows N] [FILE|-]` dispatcher
without changing pure VT I/O posture. No arguments retain the honest scaffold
status. Unknown/malformed options return 2; input I/O failures return 1. Read
raw bytes through one reusable 4096-byte buffer, not whole-file text. Add an
explicit `--replay` mode for warren-rec 1, never auto-detect it in raw input:
validate its magic/initial size, feed output payloads, skip input payloads,
and apply resize records. A 64-byte header buffer and scalar decimal parser
bound replay bookkeeping; payloads stream regardless of their declared size.
Malformed/truncated recordings return 2 without a partial dump.

The native CLI defaults to 8MiB history. A documented diagnostic
`--history-bytes` override may reduce it (0..8388608), so native/lupin replay
comparisons can use the same smaller configured cap without raising the
interpreter budget. Recording mode takes its initial size from the record;
raw size flags with replay are usage errors, not silently ignored overrides.
Argument decoding, file descriptors, replay parsing and output live in the
command boundary; src/vt remains clock-, environment- and I/O-free. Rows
cover stdin/file identity, binary bytes, options/refusals, replay output vs
input/resize, malformed lengths and a multi-chunk stream.

Lane decision for recording comparisons: reproduce the reference feeder's
external startup window title with the explicit OSC 2 seed declared in
`tests/vt/recording_setup.json`. Bind setup separately from original captured
input hashes; do not change the empty constructor or rewrite expected titles.
Each recording also runs unseeded and must differ in the title alone, making
the entire effect of the seed visible.

## Written-cell continuation prediction

Retain one scalar written bit per cell, with an approved native payload target
of 64 bytes including alignment. Blank initialization, full/end erasure and
unwritten background paint clear it; glyph output, inserted blanks and partial
erase endpoints set it. Row edits copy it and recompute the last written cell,
so discarding a distant written suffix does not invent content from erased
gaps. Wide-pair repair must retain the profile's difference between repaired
printing/editing blanks and an erase through a pair boundary.

Snapshot copies preserve the bit. Canonical history continues to encode logical
content, not a physical erasedness bitmap: materialized logical spaces are
written, background-only paint is not. The history header and wire stay the
same. Update every capacity witness and published current pane charge after
measurement; the native default ring's own framing charge is measured separately
from the larger cells. Interpreter charges keep their separate row and fixed
budget. Scalar-only Cell copies may use the language's independent value-copy
rule; allocation and alias-independence rows must guard that optimisation.

## Follow-on comparison and measurement checkpoint

The raw/file/stdin CLI and explicit bounded recording replay now exist;
input/output remains outside the pure VT module. Eight full cases passed
native and lupin. All 151 frozen census inputs passed native and lupin,
with D1-D7 selected by name; five recordings passed natively with the explicit
startup-title fixture and paired unseeded-title-only proof. The first lupin
recording exceeded the original 180-second observer timeout and later exhausted
its fixed evaluation-step budget. Both failures remain recorded. At `7450229`,
den's unseeded/seeded pair completed with the unchanged interpreter caps and
a visible 600-second wall-clock observer deadline; other full recordings remain
pending under lupin.

At `f688478`, P2 held for all 188 frozen corpus streams under bytewise and
seeded-random output-record boundaries, preserving every input/resize event.
The focused binary bundle produced 13 strict native matches and four named
report limitations, each also held to a written expectation. Remaining
composite fuzz differences stay red while finite operation-boundary probes
isolate them; neither a minimal passing probe nor a report limitation excuses
an unrelated difference.

The shortest-prefix tool verifies every earlier prefix after its bisection
hint, including a final-equal stream; observer errors are errors. Its
controlled-observer rows pass. The native/planted/reference witness is still
pending. The pinned assigned census contains 287346 Unicode 15.1 scalars,
excluding 2048 surrogate code points; the finite batched CPR sweep is prepared,
not yet run. Every non-control disagreement will be enumerated, not silently
accepted as reference agreement.

The resource driver reuses one 2752-byte mixed chunk and child-turn slices;
its full native entry feeds exactly 100000000 bytes with default 8MiB history.
Only the 4096-byte, 4096-history smoke has run so far. It shows zero retained
feed charge on native and lupin. A small native parent records absolute child
RSS, the child's pre-exec peak and the parent's inherited peak separately,
and preserves child errors/signals. The full performance/RSS witness remains
pending. Explicit checked-machine observations are validated by verdict,
not process exit: the original monolithic history entry exhausted the fixed
step budget, so semantic/allocation/chunking entries are split without raising
that budget. The original 4096-byte native/lupin split sweep is retained;
the checked split sweep uses a declared 512-byte ring that fits the fixture.

## Current comparison checkpoint and remaining take

At `f4b660b`, the complete macOS gate passed, including all 188 frozen
complete-frame comparisons, all 74 D9 original/repaired replays, bytewise/random
P2 and corpus-wide primary content/rendition/path/no-op properties. The seven
report-limited fuzz streams are explicitly LIMITED; D9's three repaired-reference
frames retain exact background cell/field/value bounds. The 37-dump reference
bundle additionally measured twenty same-SGR background controls, all agreeing:
explicit background setters win in either order with 7/27. These finite binary
bundles are not the full prepared Linux take.

The scalar plant was observed red by name and against the pinned reference at
shortest prefix AZ (two bytes), with all earlier prefixes checked; the unplanted
control agrees at all four measured prefixes. Its final-head rebase/retake is
still required. The red-first finite G6/R1 row at `5021b75` confirms a defect:
CUP(1,5) followed by U+0301 on an otherwise blank 12×2 pane stores space+acute
at column 4 but leaves extent 0 on both primary and alternate. Resizing the
primary to 6×4 then loses the mark entirely. All three named assertions failed;
no implementation correction has been made. `combine_cell` writes the mark
without updating writtenness or extent. This is outside the existing fuzz
pieces, which always introduce a combining mark with a preceding ASCII base.

Before the one prepared Linux take: settle that invariant row, add the fresh
200-seed 4096-byte comparison/P2/resize-property drive and its 5000-seed nightly
configuration, prepare all commands against one committed snapshot with fresh
targets, then run a standalone preflight. Include the assigned-scalar reference
width sweep, actual native width vector, full 100000000-byte resource/RSS witness,
remaining complete interpreter recordings, pure/native/checked gates and plants.
Retain every named divergence and failure; never use candidate output as a golden
or conceal report-limited fields. The full Linux take has not run.

> PAX corpus leg: not run, no boot fixture in this repository yet
