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
| `from_tree(shape, panes, name, focus_leaf, zoomed)` | a layout of one tab (id 1, active) built as `add_tree` builds a tab (below); a one-leaf shape makes the layout `new` makes | as `add_tree` |
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
| `add_tree(shape, panes, name, focus_leaf, zoomed)` | a tab built from a shape (below), its leaves holding `panes` in tree order, appended last; it takes the next tab id, which it answers, and the active tab does not change; its focus is the `focus_leaf`th leaf, first in its focus order and the rest in tree order | `bad_shape` (not one whole tree with a leaf for each pane, or a node out of range), `bad_id`, `duplicate_id` (a pane given twice, or live), `bad_focus` |

- **Regions.** The server applies operations inside its turn's region, so
  none keeps a value of its caller's region in the layout: a new tab is pushed
  as a copy made in the layout's own storage, a closed tab's successors move
  down in place, and a rename writes the bytes into the name the tab already
  owns (`src/layout_region_test.lu`).
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

## Border gestures

`border_at(layout, tab, cols, rows, col, row)` returns the split node on a
drawn border, or a hit with `node=-1`. Junctions belong to the ancestor's
border line. Zoomed, hidden and out-of-area borders cannot be hit.
`drag_border(layout, hit, position, cols, rows)` moves that split to an
absolute column or row using the same subtree minimums and share rounding
as keyboard resize. It answers the signed movement, or `no_border` without
changing anything. Zero displacement or a repeated clamp leaves shares
unchanged. A hit is valid only in the caller's captured layout generation;
the server cancels it on unrelated layout changes rather than trusting
reusable arena indices. Dragging never changes focus or unzooms a tab.

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

## The arena-free form

`shape_of(layout, tab)` is a tab's tree without its arena or its panes: one
node a line of the dump, in the same preorder, each a leaf or a split with
its axis and share (empty for an unknown tab). `add_tree` builds a tab from
a shape and its panes in tree order, and `from_tree` a layout of that one
tab. Every shape they take reads back the same,
`shape_of(add_tree(s)) == s`, and each checks the whole shape, the panes and
the focus before it makes anything, so a refusal leaves the layout as it was
and spends no tab id. A leaf's axis and share are always `cols` and 0; a
split's axis is `cols` or `rows` and its share in 1..9999. The layout files
are written and read through this form.

## Layout files

A layout file is one session's tabs as TOML, written by `layout save` and
read by `layout load` and `new-session -l` (CLI.md). It holds at most
1,048,576 bytes and 32 leaves, across all its tabs.

```toml
# warren layout
version = 1
active = 1

[[tab]]
name = "main"
focus = 3
zoomed = false

[tab.root]
split = "cols"
share = 5000

[tab.root.first]
cwd = "/home/me/src/warren"
command = ["vim", "notes.txt"]

[tab.root.second]
split = "rows"
share = 5000

[tab.root.second.first]

[tab.root.second.second]
cwd = "~/mail"
```

- **The file.** `version = 1` is required. `active` is the active tab's index
  from 1 (default 1). At least one `[[tab]]`.
- **A tab** takes `name` (default empty, as a new tab's), `focus`, its
  focused leaf's index from 1 in tree order (default 1), `zoomed` (default
  false), and its tree under `root`.
- **A node** is a split or a leaf. A split has `split = "cols"` or `"rows"`
  (the dump's words), may set `share` (1 to 9999, the dump's unit; default
  5000), and needs both tables `first` and `second`. A leaf is any node table
  without `split`. It may set `cwd`: an absolute path, `~` or `~/...` (from
  the session's HOME), or a path relative to the session's start directory.
  It may set `command`, the program's words with no shell between, as `--
  CMD` takes them. A leaf with no `cwd` starts in the session's start
  directory, and one with no `command` runs the configured shell.
- **The TOML.** warren's own strict subset of TOML 1.0 reads it
  (`src/config/toml.lu`): bare keys, `[a.b]` and `[[tab]]` headers, one-line
  basic and literal strings, decimal integers, booleans and one-line arrays of
  strings, by TOML 1.0's table rules. Valid TOML outside the subset is
  refused by line with its form named (`warren's TOML has no floats`), and
  every file the subset reads, it reads as Python's tomllib does
  (`tests/config/toml.table`).
- **Refusals.** A file is refused whole, by line and reason: `dev line 7: cwd
  is an integer, not a string`. A file-wide refusal (no `version`, no
  `[[tab]]`) is at line 1, a missing table or key at the line of the table
  that lacks it, and every other at the line of the key or header that holds
  what is refused. `tests/config/layout.table` holds each one.
- **Writing.** The text is canonical: the header comment, `version` and
  `active`, then each tab with `name`, `focus` and `zoomed` always written,
  then its nodes in preorder, each header followed by its keys in a fixed
  order. A string escapes `"`, `\`, U+0000 to U+001F and U+007F, and nothing
  else. A leaf gets `cwd` only when warren learnt its pane's directory (OSC 7
  or /proc), so a pane at its session's start directory is written without one
  and starts where the loading session starts; it gets `command` only when its
  pane was started with one. Writing the reading of a written file gives the
  same bytes.

### Where a layout file is

`NAME` is a file in the layouts directory, `$XDG_CONFIG_HOME/warren/layouts/
NAME.toml`, else `~/.config/warren/layouts/NAME.toml`. A NAME may not be empty,
start with `.` or hold a control byte. A word holding `/` is a file path
instead, read from the directory the verb came from when relative (`warren
layout load ./dev.toml`); at the `:` line, from the focused pane's directory.

### Saving

`layout save NAME` writes the target's session, every tab. The text goes to
`PATH.tmp`, made exclusively at 0600 (a stale one is removed first), synced
and closed, then renamed over `PATH`; an existing file is replaced. The
layouts directory is made at 0700 when it is missing (a path's directory is
never made). It prints the file's path. A destination that is a directory,
and a text past the file bound, are refused and nothing is written, so every
file save writes, load reads.

### Loading

`layout load NAME` opens the file's tabs after the target session's and
prints each new tab's id, one a line. From a shell the active tab and the
focus stay; at the `:` line the first new tab becomes active, as `:new-tab`'s
does. The file's `active` is not used. `new-session -l NAME` makes a session
whose tabs, focus, zoom and active tab are the file's.

A refused load changes nothing. Before anything is made it checks the file
(by line); every leaf's directory and program (by line, as `-c` and `--` are);
the session's 32-pane cap; every leaf getting at least one cell at the
session's size (`too small for this layout at 80x24`); and the memory budget
for all the leaves together. All slots are held before the first spawn, and
the verb waits while slots are made, as `split` does. A refusal spends no pane
or tab id. A spawn that fails after the checks ends the panes this load made
and closes its tabs; their ids stay spent.

## Rows

| row | what it holds | where |
|---|---|---|
| goldens | 59 operation scripts, each with the expected `dump_at` and every refusal, resize answer and `pane_at` query, computed by hand from this file | `src/layout_rows/goldens.lu` |
| properties | seeded random sequences of 50 operations at 20x6, 80x24, 81x25, 320x90 and 512x512, the invariants below held after every operation, and grids of every shape up to 4x4 built at each size | `src/layout_rows/properties.lu` |
| regions | every operation applied inside a region to a layout that outlives it, read back after the region's arena is reused | `src/layout_region_test.lu` |
| `toml-subset-table` | warren's TOML subset case by case: each reading, or the refusal's line and form, held to Python's tomllib on Linux | `tests/config/toml.table` |
| `layout-file-refusals` | every schema refusal of a layout file, each text valid TOML to tomllib, by line and reason | `tests/config/layout.table` |
| `layout-file-goldens` | three layouts written byte for byte as `tests/config/layout/*.toml`, each read back to its layout | `src/layout_golden_test.lu` |
| `layout-file-round-trip` | after each property sequence, the layout and hostile leaf data written, read and rebuilt with fresh ids: shapes, names, focus, zoom, the active tab and the leaf data equal, and writing the reading gives the same bytes; its first 512 files held to tomllib (`layout-files-tomllib`) | `src/layout_rows/files.lu` |
| `layout-shape-add-tree` | a tab's shape read back from the tab `add_tree` builds from it, with that tab's panes, focus, focus order, zoom and name, and each refusal leaving the layout's dump and next tab id as they were; the same for the layout `from_tree` makes, whose one-leaf tree is `new`'s layout | `src/layout_rows/shape.lu` |

The entries: `src/layout_native.lu` runs every golden and 2000 sequences at
each size, and the arena-free form's rows; `src/layout_slice.lu` runs the
goldens, or a slice of sequences at one size (`SIZE FIRST COUNT`, the same
seeds), for the checked machine and the reference interpreter, whose step
budgets hold a few dozen sequences a run (`tests/layout/rig/slices.py` sums
200 a size on the first and 50 on the second); `src/layout_test.lu` puts the
goldens, the arena-free form's rows, and four sequences with the constructed
grids at each size (one test a size, each inside the checked machine's
budget), in the ordinary `wolf test` gate.

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
