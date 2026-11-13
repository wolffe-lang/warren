# Draft for wr01: the emulator's contract (W1)

An outline for the lane that writes `src/vt`. It is exact where exactness
decides whether two implementations agree: the parser's states, the grid's
invariants, resize, and what scrollback costs. "Measured" means a census
stream under `tests/vt/census.py` shows it on the reference emulator (xterm
390); the stream's name is given so the row can be re-read. "Ruled" means
warren decides, because the reference has no answer or a wrong one.

## 0. Shape

`src/vt` is pure: no I/O, no clock, no allocation whose size the input chooses
beyond the stated caps. One value, `Vt`, is one pane's terminal.

```
new(cols, rows, scrollback_cap_bytes) -> Vt
feed(vt, bytes)                 total; never fails
resize(vt, cols, rows) -> str   empty on success; vt-size-area on refused size
                               positive sizes up to 262144 cells are accepted
take_answers(vt) -> bytes       what the terminal says back (DA, DSR, CPR, DECRPM)
take_events(vt) -> [Event]      title changed, bell, clipboard write, mode changed
dump(vt) -> text                the screen dump, format 1 (docs/SCREEN-DUMP.md)
```

`feed` never writes to the pty and never reads a clock. Everything a pane
does to the world leaves through `take_answers` and `take_events`, so the
module runs under the reference interpreter and every row is a replay.

## 1. The parser

Bytes are decoded as UTF-8 first; the state machine below runs on the result.
C1 controls are never recognised: a raw byte 0x80-0x9F is malformed UTF-8,
and the code points U+0080-U+009F arriving as UTF-8 are dropped without
effect (measured: `c1-raw-csi`, `c1-as-utf8-csi`).

### 1.1 UTF-8

| Input | Result | Evidence |
|---|---|---|
| a well-formed sequence | its code point | |
| a byte that cannot start a sequence (0x80-0xBF, 0xF8-0xFF) | one U+FFFD | `utf8-lone-continuation`, `utf8-ff` |
| a truncated sequence | one U+FFFD for the bytes consumed; the byte that broke it is processed afresh | `utf8-truncated-2`, `utf8-truncated-3` |
| a surrogate (ED A0..BF ..) | one U+FFFD for the three bytes | `utf8-surrogate` |
| an overlong form, or a value past U+10FFFF | **ruled:** one U+FFFD per maximal subpart, as Unicode recommends | the reference keeps a value that is not a character (`utf8-overlong`, `utf8-beyond`); divergence D3 |

A sequence may be split across two `feed` calls at any byte.

### 1.2 States

| State | Entered by | Bytes it consumes |
|---|---|---|
| ground | start; the end of any sequence | printable code points print; C0 executes |
| escape | ESC, from any state | one final byte, or an intermediate |
| escape-intermediate | 0x20-0x2F after ESC | intermediates, then one final |
| csi-entry | ESC `[` | a private marker `< = > ?`, a parameter byte, an intermediate, or a final |
| csi-param | a digit, `;` or `:` | digits, `;`, `:`; an intermediate; a final |
| csi-intermediate | 0x20-0x2F in a CSI | intermediates, then a final |
| csi-ignore | a private marker after a parameter; a parameter after an intermediate; more parameters or intermediates than the caps | everything up to and including the final |
| osc-string | ESC `]` | everything up to BEL or ST |
| string-ignore | ESC `P`, ESC `X`, ESC `^`, ESC `_` (DCS, SOS, PM, APC) | everything up to ST |
| string-escape | ESC inside either string state | `\` ends the string (ST); anything else abandons the string and is handled as the byte after ESC |

Rules that hold in every state:

| Byte | Effect | Evidence |
|---|---|---|
| ESC | abandons the sequence in progress and starts a new one (in a string state: enters string-escape) | `esc-inside-csi` |
| CAN (0x18), SUB (0x1A) | abandon the sequence; nothing is printed for it, and the bytes that follow are ground text | `can-inside-csi`, `sub-inside-csi` |
| any other C0 inside escape or a CSI state | executed at once; the sequence continues | `c0-inside-csi`, `lf-inside-csi` |
| a C0 inside osc-string or string-ignore | part of the string; not executed; BEL ends an OSC and does not end the others | `osc-unterminated-lf`, `dcs-unterminated-bel` |
| DEL (0x7F) | **ruled:** ignored everywhere, including OSC titles | `tests/vt/parser-reference/`: ignored in ESC/CSI/DCS; in OSC the reference changes it to `?`, divergence D8 |
| a non-ASCII scalar inside ESC or CSI, including their intermediate and ignore states | abandon the sequence and discard that scalar; following bytes are ground text | `tests/vt/parser-reference/`: `esc-nonascii`, `csi-nonascii`, the intermediate/ignore cases and replacement cases |

Caps, all **ruled** (the reference's own are not documented, and it misreads
a sequence of 31 or more parameters: divergence D4):

- 32 parameters; each a list of up to 6 colon-separated sub-parameters; each
  value saturates at 65535. A sequence with more is consumed and ignored whole.
- 2 intermediates. More: consumed and ignored.
- An OSC payload of 4096 bytes. A longer one is consumed to its terminator
  and dropped whole.
- string-ignore keeps nothing, so it has no cap.

### 1.3 Parser invariants

- **P1 total.** Every byte string is accepted. After any prefix the parser is
  in one of the ten states, holding at most the caps above.
- **P2 chunking.** `feed(a ++ b)` and `feed(a); feed(b)` leave identical
  state, answers and events, for every split, including inside a UTF-8
  sequence and inside an escape sequence.
- **P3 unknown is inert.** A well-formed sequence that is not in the scope
  table changes no state except returning the parser to ground, and prints
  none of its bytes (`csi-unknown-final`, `csi-private-unknown`,
  `csi-intermediate-unknown`, `csi-gt`, `esc-unknown`, `osc-unknown`, `dcs`,
  `apc`, `pm`, `sos`).
- **P4 answers are asked for.** Bytes enter the answer queue only from the
  query sequences in the scope table. The queue holds at most 4096 bytes; a
  query that would overflow it is dropped.
- **P5 no input reaches the host.** No sequence makes `src/vt` do I/O, read a
  file, or change anything outside its own value.

### 1.4 Event invariant

- **E1 bounded final-state notifications (ruled).** Events never allocate per
  input sequence. Until `take_events`, keep one title-changed flag (the current
  title is read from the pane), one bell flag with a count saturating at the
  largest `int`, the latest value per changed supported mode, and only the
  latest complete clipboard-write payload under the existing 4096-byte OSC
  cap. `take_events` returns final state, not a history of controls, and clears
  the pending flags and bell count. A row feeds a million title changes and
  bells under a hard region cap and requires flat allocation while feeding.

## 2. The grid

### 2.1 State

```
Vt      size, primary screen, alternate screen, which is active, pen, cursor,
        saved cursors (one per screen), modes, tab stops, scroll region,
        charsets G0 G1 and the shift, title, scrollback, parser, answers, events
Screen  rows[R]
Row     cells[C], extent, wrapped
Cell    chars (base code point, up to 2 combining marks), width, rendition,
        scalar written/erased state
Pen     rendition: flags and two colours
Colour  default | idx N | rgb R G B      (the form as set is kept)
```

`extent` is the column of the last cell written since the row was last
erased, 0 if none. `wrapped` is true when the row ended by automatic wrap, so
the next row continues the same line.

### 2.2 Invariants

They hold between any two `feed` or `resize` calls. Each names how a row can
see it broken.

- **G1 rectangular.** Every row of both screens has exactly `cols` cells.
- **G2 wide pairs.** A cell of width 2 is at column c < cols and the cell at
  c+1 has width 0; a cell of width 0 has a width-2 cell on its left. No
  operation leaves half a pair: whatever writes, erases, inserts, deletes or
  cuts one half turns the other half into a blank (measured:
  `wide-overwrite-lead`, `wide-overwrite-tail`, `wide-erase-tail`,
  `wide-dch-tail`, `wide-ich-split`). A resize that would cut a pair blanks
  the surviving half (**ruled**; the reference keeps an orphan, D5).
- **G2a one-column exception (ruled).** At cols = 1, a naturally wide
  character is kept whole (base, marks and rendition) in one width-1 cell.
  When widened, its width 2 is regenerated from the pinned width table.
  Rows must print wide at one column, widen to 2 and to 80, and narrow from
  80 to 1 and back with identical logical content. This is the only case
  where a naturally wide scalar is represented by a width-1 cell. At one
  column the server may send such a width-1 record; the client clips or
  substitutes its physical glyph. Nowhere else may it do so.
- **G3 cursor.** 1 <= row <= rows and 1 <= col <= cols. `pending_wrap`
  implies col = cols. The flag is set by printing into the last column
  whether or not autowrap is on (measured), and is consulted only when
  autowrap is on.
- **G4 region.** 1 <= top <= bottom <= rows, with top < bottom required
  only when rows > 1. A one-row pane has top = bottom = 1 (ruled and
  measured: `one-row-plain`, `one-row-region` in `tests/vt/parser-reference/`).
- **G5 tab stops** are a set of columns within 1..cols.
- **G6 extent.** 0 <= extent <= cols, and every cell past the extent is a
  blank of width 1 (it may carry colours).
- **G7 the pen is not the screen.** SGR changes the pen only. A cell's
  rendition changes only when the cell is written or erased.
- **G8 determinism.** The state is a function of the starting size and the
  ordered list of `feed` bytes and `resize` calls, and of nothing else.
- **G9 the dump is total.** `dump` succeeds on every reachable state, and
  `dump` of two equal states is byte-identical.

### 2.3 Printing

For a code point with width w (section 5):

1. w = 0 (a combining mark): added to the cell on the cursor's left, or to
   the cell under the cursor when a wrap is pending; with no such cell it is
   dropped (`combining-first-cell`, `combining-after-wide`,
   `combining-after-wrap`). A cell keeps 2 marks; later ones are dropped
   (`combining-many`). U+200D is dropped (`zero-width-joiner`). A variation
   selector is kept as a mark and does not change the width (`emoji-vs16`).
2. If `pending_wrap` and autowrap: mark the row `wrapped`, move to column 1
   of the next row (scrolling the region if on its bottom row), clear the flag.
3. Except for G2a at one column, if w = 2 and col = cols: with autowrap,
   wrap as in 2 first, leaving the
   last column as it was and outside the extent (`wide-last-column-wrap`);
   without autowrap, the character is not stored.
4. In insert mode, shift the row right by w from the cursor first; cells
   pushed past the last column are lost (`insert-mode`, `wide-insert-mode`).
5. Write the cell or pair with the pen's rendition, through the charset
   mapping of section 3.6; fix any pair this breaks (G2); extend the extent.
6. Advance by w. If that would pass the last column, stay on it and set
   `pending_wrap`.

### 2.4 What clears a pending wrap (measured, one stream each: `wrap-*`)

| Clears it | Leaves it |
|---|---|
| CR, BS, LF, IND, RI, NEL | HT (the cursor is already on the last column) |
| CUU, CUD, CUF, CUB, CUP, HVP, CHA, VPA and the other cursor moves, even to the same cell | SGR |
| EL, ED, ECH, ICH, DCH | DECSC (and DECRC restores the flag it saved) |
| IL, DL (which also move to column 1) | DECSCUSR, DECTCEM, IRM, HTS |
| DECSTBM and DECOM set or reset (which home the cursor) | OSC, DA, DSR |
| | DECAWM reset then set |

BS with a wrap pending moves to cols-1 (`wrap-bs`): the flag is cleared and
the cursor moves, not one or the other.

### 2.5 Erasing

An erased cell is a blank of width 1 with no flags and the pen's background.
The reference also gives it the pen's foreground; the dump's normalisation N1
makes that unobservable, and warren stores the background only (`bce-el`,
`bce-ed`, `bce-ech`). The same blank fills: cells opened by ICH and vacated
by DCH (`bce-ich-dch`), lines opened by IL, DL and by scrolling
(`bce-il-scroll`), and the alternate screen when it is entered
(`alt-rendition-carries`). ED 2 does not move the cursor (`ed2-cursor`). ED 3
clears scrollback and leaves the screen (`ed3`). Erasing to the end of a row
lowers the extent to the last surviving written cell; erasing a whole row
sets it to 0. A partial erase that does not reach the right edge counts its
requested blank endpoint as written. ICH counts opened blanks as written,
even beyond the old extent. Each cell retains a scalar written bit, so later
shifts can discard a distant written suffix without treating erased gaps as
content. Printing/editing pair repairs preserve writtenness where required;
an erase through a pair boundary clears the extra repaired half. These
boundaries are measured by the focused sparse-edit and full fuzz rows.

### 2.6 Regions, origin, saved cursor, the alternate screen

- DECSTBM with top >= bottom is ignored whole: no change, no homing
  (`decstbm-one-row`, `decstbm-inverted`). A bottom past the screen is the
  last row (`decstbm-past-bottom`). A valid one homes the cursor: to row 1,
  or to the region's top under origin mode (`decstbm-homes`,
  `decstbm-origin-homes`).
- CUU stops at the region's top unless it starts above the region; CUD stops
  at its bottom unless it starts below. A move from outside toward the region
  can cross it but stops at the far edge; a move away uses the screen edge
  (`cuu-stops-at-region`, `cuu-outside-region`, `cud-outside-region`, plus the
  full fuzz interaction rows). LF on the last row below a
  region does nothing (`lf-below-region`). IL and DL outside the region do
  nothing (`il-outside-region`).
- Under origin mode, addressing is relative to the region and clamped to it
  (`origin-clamps`).
- DECSC saves position, pen, origin mode, the pending wrap and the charsets;
  DECRC restores them (`decsc-rendition`, `decsc-origin`,
  `wrap-decsc-decrc`). DECRC with nothing saved homes the cursor and resets
  the pen (`decrc-never-saved`).
- Mode 1049: set saves the cursor, switches to the alternate screen and
  clears it to the pen's background, without moving the cursor. The clear
  cancels the active pending wrap; reset switches back and restores the saved
  cursor, including its pending wrap (`alt-1049-restores-cursor`). Reset does
  not clear the shared alternate contents: a later mode-47 entry finds them.
  Set again while set clears again (`alt-1049-twice`). Modes 47 and 1047 share
  the one alternate screen; 47 neither saves nor clears (`alt-47-keeps`). The
  pen, the region and the modes are shared by the two screens
  (`alt-rendition-carries`, `alt-region-shared`).
- RIS resets terminal/parser state, both screens, scrollback, modes, tabs,
  saved cursors and queued answers, but keeps the title (`ris` in
  `tests/vt/census.txt`). The title is the window's, not the screen's.
  DECSTR resets the pen, region, origin, insert mode and cursor visibility,
  and leaves the screen and the cursor's position (`decstr`).

## 3. Scope: the sequences W1 serves

The list, with the document's section for each, is in the prediction
(`notes/wr00-the-map.md`, "W1's scope"). Three matters in it are rulings.

### 3.1 Where warren differs from the reference, by name

| | The reference | warren | Why |
|---|---|---|---|
| D1 | `SGR 4:3` sets foreground 0 and no underline (`sgr-underline-colon`) | `4:0` clears underline, `4:1` to `4:5` set it | yew writes `4:3`; the reference at this version predates the form |
| D2 | `SGR 58;2;r;g;b` reads the tail as bold, dim, italic (`sgr-underline-colour`) | 58 and 59 are consumed with their arguments and have no effect | yew writes it; misreading it is the visible bug PAX's console has today |
| D3 | overlong and out-of-range UTF-8 kept as non-characters | U+FFFD | section 1.1 |
| D4 | 31 or more parameters misread | ignored whole past 32 | section 1.2 |
| D5 | an orphan half of a wide character after a narrowing resize | a blank | G2 |
| D6 | no reflow on resize | section 4 | the survey: every multiplexer reflows |
| D7 | `SGR 53` (overline) ignored, mode 2026 unknown | 53 consumed without effect; 2026 stored and reported | yew sets 2026 around every frame |
| D8 | DEL inside an OSC title becomes `?` (`tests/vt/parser-reference/osc-del.in`, title `613f62`) | DEL is silently dropped, yielding title `6162` | titles are display text; dropping the control is cleaner than adding a visible question mark |

Rows for D1 to D8 compare with written expectations, never with the
reference, and a corpus stream that exercises one is compared under that
divergence's name or not at all.

### 3.2 SGR details (measured)

`38;5;N` and `38:5:N` are the same; `38;2;R;G;B`, `38:2:R:G:B` and
`38:2::R:G:B` are the same (`sgr-colon-*`). An index past 255 or a component
past 255 leaves the colour unchanged (`sgr-256-out-of-range`,
`sgr-rgb-out-of-range`). A truncated `38;5` sets index 0 and a truncated
`38;2;R;G` takes the missing component as 0 (`sgr-truncated-*`). 21 is double
underline, a flag of its own; 22 clears bold and dim; an empty SGR is a reset.
After a colour's arguments the list continues (`sgr-mixed-after-38`).

### 3.3 Proposed beyond the decided subset

The decided subset names cursor motion, erase, insert and delete, regions,
SGR, the alternate screen, paste, mouse, UTF-8, titles, cursor shape, and the
DA and DSR answers. A program told `TERM=xterm-256color` can also be led to
send the following, and each is cheap; without them ordinary programs break:

- the DEC special graphics set through `ESC ( 0`, `ESC ) 0`, SO and SI
  (line drawing in every curses program) (`charset-*`);
- REP, SU, SD, CHT, CBT, HPR, VPR, CNL, CPL, ECH, HTS, TBC, NEL, IND, RI,
  DECALN (all measured in the census);
- modes 1 (cursor keys), 6, 7, 12, 25, 66 or `ESC =`/`ESC >` (keypad), 1004
  (focus), 1007, 2026, and ANSI 4 and 20;
- DECRQM answers for the modes it stores, so a program can ask rather than
  guess.

Modes 1000, 1002 and 1003 select one mouse-tracking mode. Setting one clears
the other two; resetting any of the three clears that tracking selector,
without resetting the independent SGR coordinate format or focus mode.

## 4. Resize

The reference does not reflow, so most of this section is ruled. It is
written as invariants first because the algorithm has several correct forms
and they must all satisfy the same rows.

**Terms.** A *line* is a maximal run of rows joined by `wrapped`. Its
*content* is the cells of those rows up to each row's extent (a wrapped row's
extent is the whole row). The *text* of a pane is its scrollback's lines
followed by the primary screen's lines. The original-screen snapshot preserves
per-cell written bits. Canonical history stores logical content rather than a
physical erasedness bitmap: its materialized logical spaces are written,
while background-only paint remains unwritten. This does not change the
history header or wire encoding.

- **R1 content is kept.** On the primary screen, a resize changes no line's
  content, except that whole oldest fragments may leave scrollback to stay
  under the cap. Nothing is cut at the right edge.
- **R2 the cursor keeps its place.** The cursor stays on the same cell of
  the same line, or, when it sat past the content, the same distance past it,
  clamped to the new width. If that logical cell lies outside the visible
  suffix chosen by R5, project the displayed cursor to the nearest visible
  cell, retaining the original logical anchor across resize-only sequences.
  The next nonempty feed commits the projected position. For example, after
  shrinking 24 rows to 1, regrowing without feed restores the original cursor
  if no text was evicted; feeding a byte before regrowing instead commits the
  visible position. Eviction must never resurrect an abandoned anchor.
- **R3 path independence.** For any sizes a and b, resizing to a and then to
  b gives the same text, the same cursor place and the same rows on screen as
  resizing straight to b, provided no fragment left scrollback on the way.
- **R4 wide characters are not split.** A wide character that would start in
  the last column moves whole to the next row; the cell it leaves is outside
  that row's extent, so it is not content and R3 survives it.
- **R5 the bottom is anchored.** After a resize the last non-blank row of
  the text at or below the cursor sits where it did relative to the bottom,
  as far as the new height allows: when rows are lost they go to scrollback
  from the top; when rows are gained they come back from scrollback (measured
  on the reference, which does this much: `resize-shorter`, `resize-taller`).
  **Ruled:** when older history is exhausted, existing text stays top-anchored
  and remaining new rows are blank padding at the bottom; no top padding is
  manufactured just to preserve a former bottom distance. Rows cover 4x1 to
  4x3 with no history, exactly one older line (pulled above the current text),
  and more history than the added rows.
- **R6 the alternate screen is not reflowed.** It is cut or padded at the
  right and the bottom, top-left anchored, and the cursor is clamped
  (measured: `resize-alt`). The primary screen behind it is reflowed at the
  same moment, so leaving the alternate screen never shows a stale width.
- **R7 what a resize resets.** The region becomes the whole screen
  (measured: `resize-region-tabs`). Tab stops are kept, and no stops are
  added for new columns when the stops were set by hand (measured, same
  stream); **ruled:** while the stops are still the default eights, new
  columns continue the eights. The pending wrap is cleared. Saved cursors are
  moved by R2.
- **R8 a resize to the same size changes nothing.**

Rows: the alternate-screen and bottom-anchor rows compare with the reference.
R1 to R4 are property rows: for each corpus stream and each fuzz seed, random
resize sequences ending at the same size must agree with one resize, and with
the text taken before any. tmux reflows, so a few streams are also compared
with it as the second black box, text only.

## 5. Width

One table, generated from the Unicode Character Database at a pinned
version, decides w for every code point: 0 for combining marks (general
categories Mn, Me), for U+200B to U+200F and the other default-ignorable
format characters; 2 for East Asian Wide and Fullwidth and for the emoji
presentation ranges; 1 otherwise. **Ruled:** the version is the one the
reference's C library carries, so the two can agree; W1's first row sweeps
every assigned code point through the reference (print it, read the cursor
column) and records every disagreement by name. The client is told nothing
about this table: an outer terminal with other width rules (PAX's console
draws every code point in one cell) is the renderer's problem, not the grid's.

## 6. Scrollback and what it costs

- **Storage follows logical lines, not physical rows.** A line leaving the
  top of the primary screen is encoded unwrapped, whatever width it was
  wrapped at, in bounded continuation fragments. Each fragment carries the
  same stable logical-line ID and its starting cell offset. Reflowing history
  therefore needs no rewrite; only visible rows are rebuilt, and a history
  view wraps the surviving logical content on demand.
- **Encoding.** Each fragment has a 24-byte little-endian header, in order: total
  encoded length u32, previous-record length u32, stable line ID u64,
  logical start-cell offset u32, and flags u32 (unused bits must be zero).
  Its text is UTF-8, with one 12-byte record per run of equal rendition.
  Trailing blanks past the extent are not stored unless they carry a
  background. Previous lengths permit reverse traversal across ring wrap
  without an unbounded per-line index.
- **The cap** counts exactly those bytes. Default 8 MiB a pane. When a new
  fragment would pass it, whole encoded fragments leave from the oldest end
  until it fits; an encoded record is never retained in part.
- **S1** stored bytes <= cap, always.
- **S2** one encoded fragment holds at most 65536 logical content cells,
  without splitting a wide glyph. A longer logical line continues in another
  fragment with the same line ID and its next cell offset. Whole-fragment
  eviction may remove only the oldest logical prefix. A reader can therefore
  meet a first surviving fragment whose offset is nonzero: it shows the
  surviving suffix from its first cell, without inventing prefix spaces or
  text, and preserves original offsets for addresses. It never renumbers that
  suffix to offset zero. This bounds an endless line without an unbounded
  fragment-ID index. After 2^32 logical cells, a line continues under a fresh
  logical-line ID at offset zero; input is never refused and old addresses
  never wrap to the new line.
- **S3** lines are numbered from 0 for the life of the pane and never
  renumbered: copy mode, search and a saved view address (line number, cell),
  which a resize and an eviction leave meaningful.
- **S4** only the primary screen feeds scrollback, and only when the region
  is the whole screen or starts at row 1. The alternate screen never does.
  ED 3 empties it.

Costs to hold, as rows with numbers taken on one machine and compared only
with that machine: appending a line is O(its length); eviction is O(1)
amortised; a resize is O(rows on screen + the retained logical lines they
hold), independent of unrelated history lines. A logical line includes its
retained continuation fragments, so an endless visible line can require
lookback up to the configured history cap. The allocation budget counts the
fixed-capacity encoded history ring, peak screen/workspace capacities and
all retained arena growth buffers; replaced arena buffers are not claimed
freed. The canonical resize deque has
an explicit additional bound of the configured history cap plus 48 bytes per
peak cell before geometric rounding; it is not treated as free duplication
of history. Backing capacity is reused on shrink and on regrowth within the
previous peak, with no further charge.
Growth is bounded by the protocol's 262144-cell area ceiling. Tests repeat
small→large→small→large under native and interpreter region caps and require
charge to plateau after capacity is reached. A plain 80-byte, one-rendition
line costs 116 bytes including its header and run, so 8 MiB holds roughly
72,000 such lines; this is an estimate, not a line-count promise. Encoding
rows require reverse traversal across ring wrap, exactly one fragment evicted
at the cap boundary, and a stable ID surviving reflow. Additional S2 rows
encode 65537 cells, split a valid 262144-column physical row, preserve one ID
across fragments, and start a reader at a line whose prefix was evicted
without inventing the missing content. A counter seam crosses the 2^32-cell
boundary without feeding billions of cells.

## 7. Rows

| Row | Against | Red-first plant |
|---|---|---|
| unit rows for each operation, native and under the reference interpreter | written | one per invariant G1 to G9 |
| the eight harness cases | the reference, whole dump | |
| the census (about 150 streams) | the reference, whole dump, D1 to D7 by name | a pending-wrap entry flipped |
| the recorded corpus, at its end and at every resize point | the reference | |
| the fuzz corpus: 200 seeds of 4 KiB per pull request, 5000 nightly | the reference | a dropped continuation cell |
| chunking: every stream fed one byte at a time and at random splits | itself (P2) | a parser state lost across calls |
| the first divergent prefix: a bisecting tool that names the shortest prefix of a stream at which the two dumps differ | the reference | |
| resize properties R1 to R4, R8 | themselves | a reflow that drops a row's last cell |
| resize rows R5, R6, R7 | the reference | |
| scrollback: S1 to S4, ED 3, the cap under a 100 MB stream with a hard memory limit | written | an eviction that leaves a partial line |
| answers: DA1, DSR 5 and 6, DECRPM | written | |
| hostile: malformed UTF-8, a megabyte of ESC, unterminated strings, saturating parameters; time and memory bounded | written, and P1 | |
| the width sweep | the reference | |
| `warren vt-dump [--cols N --rows N] [FILE]` prints format 1; exit 0, or 2 for usage | the harness itself | |

## 8. What px125 can change

The emulator is the same on every host, so nothing PAX's console lacks
changes this contract. Two answers change neighbours of it: the console
draws one cell per code point (the client's renderer must place the cursor
after every wide or combining character rather than trust the terminal's
advance), and it shows 16 colours (the renderer downsamples; the grid keeps
what was set).
