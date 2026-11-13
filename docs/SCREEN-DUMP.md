# The screen dump

One text form describes a terminal screen, whether it came from the reference
emulator or, from W1 on, from warren's own (`warren vt-dump`). Emulator rows
compare two of them. The form is line-oriented UTF-8 text so that a failing
row can be read and a diff of two dumps means something.

```
warren-screen 1
size 80 24
cursor 3 5 shape=2 visible=1 pending-wrap=0
region 1 24
tabs 9,17,25,33,41,49,57,65,73
title 68656c6c6f
mode alternate-screen-1049 0
mode autowrap 1
...
row 1 extent=6
1 1 U+0041 -
2 2 U+4E2D bold,fg=idx:196
3 0 - bold,fg=idx:196
4 1 U+0065+U+0301 -
5-80 1 U+0020 -
row 2 extent=0
1-80 1 U+0020 bg=rgb:1:2:3
```

| Line | Meaning |
|---|---|
| `size C R` | columns and rows |
| `cursor R C shape=S visible=V pending-wrap=W` | 1-based and absolute, whatever origin mode says; `S` is the DECSCUSR number; `W` is 1 when the cursor sits on the last column with the next character due to wrap |
| `region T B` | the scroll region |
| `tabs` | tab stop columns, or `-` |
| `title` | the title's bytes in hex, or `-` |
| `mode NAME V` | 1 set, 0 reset, `?` not known to the emulator; sorted by name |
| `row N extent=E` | `E` is the column of the last cell written since the row was last erased; 0 for a row never written. Cells past it are blanks, but may carry colours |
| `C W CHARS ATTRS` | one cell, or `C1-C2` for a run of identical one-column cells |

A cell's width `W` is 1, 2 for the first half of a wide character, or 0 for
its second half, whose `CHARS` is `-` and whose `ATTRS` repeat the first
half's. `CHARS` is the base code point and any combining marks, joined with
`+`. `ATTRS` is `-` or a comma list in this order: `bold`, `dim`, `italic`,
`underline`, `double-underline`, `blink`, `inverse`, `invisible`, `strike`,
then `fg=` and `bg=`. A colour is `idx:N` (0 to 255) or `rgb:R:G:B`: the form
in which it was set is kept, so palette entry 196 and the same red set as
24-bit colour are different.

## How the reference emulator is read

It is run under a virtual X server and spoken to only through its own pty and
its print-screen file (`tools/oracle/`). Two passes replay the same bytes into
two fresh emulators.

**Pass A** asks: the cursor (CPR and DECCIR, which must agree), the pending
wrap (DECCIR), tab stops (DECTABSR), the cursor shape and scroll region
(DECRQSS), each mode (DECRQM), the title and size (window reports), one
checksum per cell (DECRQCRA, configured to give the code point), and a
print screen with renditions.

Print screen has two limits, both measured. It stops each row at the last
written cell. And it does not state every cell's rendition: a plain cell
after a bold one with the same colours is printed with no reset, as if it
were bold, and a cell that was never written is printed with none at all.

**Pass S** closes both. After the replay the screen is widened to three
times its columns, and every cell is copied (DECCRA) into the fresh columns
on the right, each behind a separator blank on a background no stream uses.
Print screen writes a rendition whenever the colours change, so it must then
state every cell's. Pass A's renditions are not used; where pass A did write
one outright before a character, the two passes must agree, and a dump on
which they do not is refused.

The per-cell checksum tells a wide character's second half (it answers zero)
from a blank. Because the emulator's replacement for a malformed byte and any
code point whose low sixteen bits are zero also answer zero, the layout of a
row is searched for and must be unique.

## Recording fixture setup

The reference starts its Python feeder as the terminal's command, so its
window initially has title `python3`. Recording files encode program bytes
and sizes, not that host window setup. `tests/vt/recording_setup.json`
therefore declares an explicit startup OSC 2 seed for recording comparisons.
The seed is bound in the reference index and inserted as output after the
initial size, before any recorded event. Neither the empty-title constructor
nor the title comparison is changed. A paired row runs each recording
without the seed and requires its only difference to be the title, then
compares the seeded whole screen normally. This is fixture setup, not a
normalisation that silently ignores a field.

## Focused report limits

The pinned binary measurements in `tests/vt/reference/interactions` retain
all input bytes, raw A/S replies, print bytes and hashes. Their comparator
reports these rows as **reference report cannot express this**, not as
reference agreement; separate written expectations hold warren to its rules.

- **RPT-TABS-COLUMN-ONE:** `CSI 3 g; ESC H` sets a stop at column 1,
  but DECTABSR returns the same empty list as `CSI 3 g` alone. Column 2
  is reported normally. Warren retains the column-1 stop.
- **RPT-BRIGHT-BOLD-COLOUR:** both `CSI 1;91;42 m X` and
  `CSI 1;38;5;9;42 m X` print `CSI 0;1;31;42 m X`. The report loses
  the distinction between the stored bright palette form and a dark colour
  rendered bright through bold. DECSC/DECRC produces the same result.
  Warren retains palette entry 9, bold and palette background 2.

These are limits of the report, not permission to ignore tab or colour
fields generally. Direct RGB, RGB save/restore and RGB 1049 restoration
remain strict comparisons. Minimal ECH, EL and DCH right-edge probes also
remain strict; they do not explain or excuse other extent differences.

## Normalisations

Every place where a dump is not compared as written, by name.

| Name | What | Why |
|---|---|---|
| N1 blank-foreground | a blank cell with no underline, strike or inverse is compared without its foreground | the reference gives erased cells the pen's foreground too, resolved through bold; nothing shows it |
| N2 precompose-off | the reference runs with `precompose: false` | a base and a combining mark stay two code points, as sent |
| N3 absolute-cursor | the cursor is absolute | CPR is relative under origin mode; DECCIR is not |
| N4 replacement | the reference's cell for a malformed byte is reported as `U+FFFD` | print screen writes it as `#`; its checksum (zero) tells it from a real `#` |
| N5 widths-as-run | widths are whatever the reference decides, from its C library's tables | recorded, not asserted; W1 pins a Unicode version against it |

## What the mechanism cannot show

- The screen that is not active (the normal screen while the alternate one is
  shown, and the reverse), and the saved cursor: only by a stream that
  switches or restores.
- Scrollback. Lines that left the top are seen only when a taller screen
  pulls them back.
- Whether a blank cell was erased or written as a space, beyond what the row's
  extent says.
- More than the reference keeps: it holds two combining marks per cell and
  drops a zero-width joiner.
- Character set state (G0 to G3), except through what later text draws.
- Underline styles and colour, overline, and synchronized output: the
  reference at this version does not have them.
- Anything in a stream that uses one of the two separator colours as a
  background; such a dump is refused by name rather than guessed.
- A wide character cut in half by a narrower screen. The reference keeps an
  orphan half that cannot be copied whole; such a dump is refused.
- A control sequence with 31 or more parameters: the reference misreads it
  (measured on SGR). Corpora stay well below that.
