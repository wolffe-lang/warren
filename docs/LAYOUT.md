# The layout

`src/layout` holds a session's tabs and, inside each tab, a tree of splits
whose leaves are panes. It is pure: no I/O, no clock, no process. It knows
pane ids, never ptys, emulators or clients. It answers geometry for the
compositor and applies the operations the key table and the command socket
ask for, each of which either changes the layout or answers a named refusal
and changes nothing.

This file is the module's contract. The golden rows in `src/layout_rows/`
were written by hand from it before the code.

## Data

- A **layout** is a list of tabs, the id of the active tab, and the next tab
  id to hand out. Tab ids start at 1 and are never reused.
- A **tab** has an id, a name (UTF-8 bytes, kept as given), an arena of
  nodes with the index of its root, the focused pane, a zoom flag, and the
  focus order: every pane of the tab exactly once, most recently focused
  first. The focused pane is always the first of the focus order.
- A **node** is a leaf (one pane) or a split. A split has an axis, two
  children (`first`, `second`) and a share. Every node records its parent
  (`-1` for the root). Freed arena slots are reused; nothing in the arena
  outlives its tab.
- **Pane ids** come from the caller (the server assigns them) and must be at
  least 1. An id is unique across every tab while its pane lives.
- **Axes.** `cols` puts the children side by side, the border between them
  a vertical line of cells; `rows` stacks them, the border a horizontal line.
- **Shares** are the first child's part of a split's extent, in units of
  1/10000, always in 1..9999. A new split has share 5000. Shares are kept,
  never recomputed from a size, so a layout scales with the terminal.

## Geometry

Every query takes the size of the tab area in cells, `cols` by `rows`, with
the bar's lines already excluded. Cells are 1-based: column 1 is the left
edge and row 1 the top. A rect is `col,row` (its top-left cell) and
`cols x rows`.

The root takes the whole area. A split along an axis of extent `E` (its
columns for `cols`, its rows for `rows`) with minimum `m` (2 for `cols`,
1 for `rows`) divides its rect as follows:

- If `E >= 2m + 1`, the first child gets
  `a = min(max(floor((E - 1) * share / 10000), m), E - 1 - m)` cells along
  the axis, one border cell follows, and the second child gets the rest,
  `E - 1 - a`. Across the axis both children span the split's whole rect.
- Otherwise the first child takes the split's whole rect, every pane under
  the second child is **hidden**, and there is no border.

The minimum binds along a split's axis only. A hidden pane has the
zero-area rect `0,0 0x0`; nothing about it changes, so it comes back with
its share intact when the area grows. Growing the area only reveals: a pane
visible at one size is visible at every larger one. (It is not always as
large: when a split's second child appears, the first gives up its share.)

When a tab is **zoomed**, the focused pane's rect is the whole area, every
other pane is hidden, and there are no borders.

- `rects(layout, tab, cols, rows)` answers one rect per pane of the tab, in
  tree order (a split's first subtree before its second), hidden panes
  included.
- `borders(layout, tab, cols, rows)` answers one border per split that
  shows both children, in preorder (a split before the splits inside it):
  its top-left cell, its length, and the split's axis (`cols`: the border
  runs down from that cell; `rows`: it runs right).
- `pane_at(layout, tab, cols, rows, col, row)` answers the pane whose rect
  holds the cell, or -1 for a border cell, a cell outside the area or an
  unknown tab.

The rects of the visible panes and the cells of the borders tile the area
exactly: no gap, no overlap, nothing outside.

## Operations

Each operation changes the layout in place and answers nothing, or answers
a refusal and leaves the layout exactly as it was. Refusals are error-row
tags; the table lists them in the order they are checked. Operations that
need geometry take the tab area's size, as the queries do, and use the
unzoomed geometry.

| operation | effect | refusals, in order |
|---|---|---|
| `new(pane, name)` | a layout of one tab (id 1) with one pane | `bad_id` |
| `split(tab, pane, axis, new_pane, after, cols, rows)` | the pane's leaf becomes a split at share 5000 along `axis`, the new pane second if `after`, first otherwise; focus moves to the new pane | `bad_id`, `no_pane` (also for an unknown tab), `duplicate_id`, `too_small` (the pane is hidden, or its extent along the axis is below `2m + 1`) |
| `close(pane)` | the pane's parent split is replaced by the sibling subtree; if the pane had focus, focus goes to the most recently focused survivor; a tab's last pane closes the tab | `no_pane`, `session_empty` (the last pane of the last tab: the server ends the session instead) |
| `focus(tab, direction, cols, rows)` | focus moves to the neighbour in that direction (below) | `no_tab`, `no_neighbour` |
| `focus_pane(pane)` | the pane's tab becomes active and the pane takes focus | `no_pane` |
| `focus_next(tab)`, `focus_previous(tab)` | focus moves to the next or previous pane in tree order, wrapping | `no_tab` |
| `resize(pane, direction, cells, cols, rows)` | the border on that side of the pane moves (below); answers how many cells the pane grew | `no_pane`, `no_border` |
| `zoom(tab)` | toggles the zoom flag | `no_tab` |
| `equalize(tab)` | every split's share becomes 5000 | `no_tab` |
| `new_tab(new_pane, name)` | a tab with one pane, appended last, takes the next tab id and becomes active; answers its id | `bad_id`, `duplicate_id` |
| `close_tab(tab)` | the tab and its panes go | `no_tab`, `last_tab` |
| `select_tab(n)` | the tab at 1-based position `n` becomes active | `no_tab` |
| `select_tab_id(tab)` | that tab becomes active | `no_tab` |
| `next_tab()`, `previous_tab()` | the next or previous tab becomes active, wrapping | none |
| `rename_tab(tab, name)` | the tab's name becomes `name` | `no_tab` |

- **Focus order.** Whenever a pane takes focus (a split's new pane, a new
  tab's pane, any focus operation) it moves to the front of its tab's focus
  order. A closed pane leaves it.
- **Zoom follows focus.** A focus operation does not unzoom; the newly
  focused pane is the one shown. `split`, `close`, `resize` and `equalize`
  unzoom their tab first (when they succeed).
- **The active tab after a close.** When the active tab closes, the tab
  that takes its position becomes active, or the new last tab when it was
  last. A split, close or resize in another tab does not change which tab
  is active; `focus_pane` does.

### Directional focus

From the focused pane's rect, the candidates are the visible panes just
past the border on that side: for `right`, the panes whose first column is
the focused pane's last column plus 2; for `left`, those whose last column
is its first column minus 2; `down` and `up` likewise with rows. A candidate
qualifies when its span across the direction, widened by half a cell at
each end, contains the focused pane's centre line. For left and right, with
the focused pane on rows `r .. r+h-1`, that is

    2 * cr - 1  <=  2 * r + h  <=  2 * (cr + ch) + 1

for a candidate on rows `cr .. cr+ch-1` (columns likewise for up and
down). Two candidates qualify only when the centre line falls exactly in
the middle of the border cell between them; then the one focused more
recently wins. A hidden focused pane has no neighbour. Directions: `left`,
`right`, `up`, `down`.

### Resize

`resize(pane, direction, cells)` moves the border on the pane's `direction`
side by `cells` in that direction, so a positive count grows the pane and a
negative one shrinks it. The border is that of the nearest ancestor split
along the direction's axis (`cols` for left and right) that has the pane on
the near side (in its first child for `right` and `down`, in its second for
`left` and `up`). It is `no_border` when there is none, or when that split
is hidden or shows no border at this size.

With the split's first child at `a` cells, the target is `a + cells`
(`right`, `down`) or `a - cells` (`left`, `up`), clamped in the direction of
travel against each side's minimum: the extent below which something in that
subtree would hide (a pane's own minimum; for a split along the same axis the
two children's minimums plus the border; across it, the larger of the two).
A border never moves into a side already at or below its minimum, and a
resize never hides a pane. The new share is the smallest that gives the
target, `ceil(target * 10000 / (E - 1))`, kept in 1..9999; when the border
does not move, the share does not change. The answer is the number of cells
the pane grew (negative when it shrank, 0 when the clamp held it).

## The canonical dump

`dump(layout)` is the canonical text form of a layout: one line for the
layout, then each tab in order, a line for the tab and one line per node in
preorder, indented two spaces per level below the tab. Every line ends with
a newline.

```
layout tabs=2 active=1 next=3
tab 1 focus=3 zoomed=0 order=3,2,1 name="main"
  split cols share=5000
    pane 1
    split rows share=5000
      pane 2
      pane 3
tab 2 focus=4 zoomed=0 order=4 name="logs"
  pane 4
```

- `layout tabs=N active=ID next=ID`: the tab count, the active tab's id and
  the next tab id.
- `tab ID focus=PANE zoomed=0|1 order=P,P,... name="..."`: the name's bytes
  between quotes, with `\"` for a quote, `\\` for a backslash and `\xHH`
  (lowercase) for a byte below 0x20 or 0x7f; other bytes as they are.
- `split cols|rows share=S` and `pane ID`.

`dump_at(layout, cols, rows)` is the same text with geometry at a size: the
layout line ends ` size=COLSxROWS`, a visible pane's line ends
` at=COL,ROW size=COLSxROWS`, a visible split's line ends
` at=COL,ROW size=COLSxROWS border=B` where `B` is the border's column
(`cols`) or row (`rows`), or `none` when the second child is hidden, and a
hidden pane or split (including every split of a zoomed tab) ends ` hidden`.

```
layout tabs=1 active=1 next=2 size=80x24
tab 1 focus=3 zoomed=0 order=3,2,1 name="main"
  split cols share=5000 at=1,1 size=80x24 border=40
    pane 1 at=1,1 size=39x24
    split rows share=5000 at=41,1 size=40x24 border=12
      pane 2 at=41,1 size=40x11
      pane 3 at=41,13 size=40x12
```

Two layouts are equal exactly when their dumps are, whatever their arenas
hold. The layout files of a later milestone build on this form.

## Rows

| row | what it holds | where |
|---|---|---|
| goldens | 59 operation scripts, each with the expected `dump_at` and every refusal, resize answer and `pane_at` query, computed by hand from this file | `src/layout_rows/goldens.lu` |
| properties | seeded random sequences of 50 operations at 20x6, 80x24, 81x25, 320x90 and 512x512, the invariants below held after every operation, and grids of every shape up to 4x4 built at each size | `src/layout_rows/properties.lu` |

The entries: `src/layout_native.lu` runs every golden and 2000 sequences
at each size; `src/layout_slice.lu` runs the goldens, or a slice of
sequences at one size (`SIZE FIRST COUNT`, the same seeds), for the checked
machine and the reference interpreter, whose step budgets hold a few dozen
sequences a run (`tests/layout/rig/slices.py` sums 200 a size on the first
and 50 on the second); `src/layout_test.lu` puts the goldens and five
sequences a size in the ordinary `wolf test` gate.

The invariants:

1. The rects of the visible panes and the borders tile the area exactly,
   `rects` names every pane of the tab once, and `pane_at` agrees: a
   rect's corner cells answer its pane, a border's first cell -1.
2. Every pane id appears once across all tabs; every tab has a pane; each
   tab's focus is one of its panes and first in its focus order, which
   holds each of its panes once; the active tab exists; the arena's parent
   and child links agree.
3. Shares stay in 1..9999; only `resize` (one split) and `equalize` change
   an existing share; a pane visible at a size is visible at larger sizes.
4. A split then the close of the new pane gives back the original layout
   (unzoomed, since a split unzooms).
5. A resize by `+n` then `-n` that the clamp did not touch gives back the
   same rects; every resize answers a growth of the sign it was asked for,
   and no more cells than asked.
6. In a grid (every column span meets every row span), focus in a direction
   then in the opposite one comes back.

A refusal leaves the layout equal to what it was, checked after every
refused operation.
