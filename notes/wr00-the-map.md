# wr00: the map (W0, first half)

The first lane of warren: the scaffold, the oracle and its harness, the
survey, the corpus, the `TERM` question, the prediction for W1, and the two
drafts (the emulator's contract and the wire protocol) that the next lanes
are written from.

## Prediction

Written before the harness's first commit on this branch, from an exploratory
take against the reference emulator. What was already seen is said so.

1. **The oracle.** xterm, run headless under a virtual X server and spoken to
   only through its pty, can produce a cell-for-cell dump: characters, each
   rendition, colours in the form they were set, cursor position, shape and
   visibility, the pending wrap, the scroll region, tab stops, the title and
   the modes. *Seen in exploration:* print screen alone cannot do it. It stops
   each row at the last written cell, and it does not write a reset before a
   plain cell that follows a cell with a rendition and the same colours. I
   predict a second pass that spreads the cells apart behind separator cells
   closes both gaps, and that a rule check can then hold the first pass's
   print to the measured rule on every case.
2. **Hand-written expectations.** Three screens written from the control
   sequence document before any take (`sgr`, `wide`, `erase`) will match the
   oracle cell for cell. I expect to be wrong about at least one mode's
   default. *Seen:* mode 1048 always answers "set"; it is not screen state and
   left the dump.
3. **The mutation rows.** An injected wrong attribute, a wrong cursor
   position and a dropped wide-character continuation will each go red at
   their own named row (`cell-attribute`, `cursor-position`,
   `wide-continuation`), on live dumps and on the committed ones.
4. **Determinism.** Two takes of every case, every census stream and every
   fuzz seed will be identical. If any is not, it is a timing dependence in
   the harness, not in the emulator.
5. **The census** (about 150 small streams) will show the reference emulator
   differing from what a reader of the document would guess in a handful of
   places: which operations clear a pending wrap, what an erased cell keeps,
   malformed UTF-8, and SGR forms newer than the emulator's version. Each one
   becomes a rule or a named divergence in the emulator's contract.
6. **tmux as the second black box** will agree with the reference emulator on
   the text and cursor of the harness cases. Its default for a session shared
   by two clients of different sizes is `latest`, per its manual; a row will
   show it and show `smallest`.
7. **The corpus.** yew, quarry and pelt record on a pty inside the reference
   emulator and replay to the same final screen on every take. den has no
   pager, so its row is long plain output. Recordings stay under a few
   hundred kilobytes each.
8. **The scaffold** builds on Linux and macOS with the standard library
   staged at the pin in place of the bundled one. *Seen:* the first build was
   refused until the package declared the `fs` capability, and the reference
   interpreter wants a `main`, so the pure modules have a test of that form.
9. **Not expected to work in this lane:** nothing on PAX is measured here;
   zellij and herdr are surveyed from their documents and not run.

## W1's scope, predicted

Committed before any emulator code. "Document" is the control-sequence
document shipped in the reference emulator's own package (patch 390; digest
in `docs/SOURCES.md`); the section is its heading. ECMA-48 section numbers
are given where the function is ECMA's. **S** = served (changes state),
**A** = answered, **C** = consumed whole with no effect.

### Single-character functions

| Sequence | | Notes |
|---|---|---|
| BEL | S | an event, not a cell |
| BS, HT, LF, VT, FF, CR | S | VT and FF act as LF; ECMA-48 8.3 |
| SO, SI | S | invoke G1, G0 |
| other C0, DEL | C | |
| CAN, SUB | S | abandon a sequence in progress |

### Controls beginning with ESC

| Sequence | | Notes |
|---|---|---|
| `ESC D` IND, `ESC E` NEL, `ESC H` HTS, `ESC M` RI | S | ECMA-48 8.3 |
| `ESC 7` DECSC, `ESC 8` DECRC | S | |
| `ESC =` DECKPAM, `ESC >` DECKPNM | S | a mode the key encoder reads |
| `ESC c` RIS | S | |
| `ESC # 8` DECALN | S | |
| `ESC ( C`, `ESC ) C` with C = `B` or `0` | S | ASCII and DEC special graphics only; other sets C |
| `ESC Z` DECID | A | as DA1 |
| `ESC N`, `ESC O`, `ESC l`, `ESC m`, `ESC n`, `ESC o`, `ESC |`, `ESC }`, `ESC ~`, `ESC SP F/G`, `ESC # 3/4/5/6`, `ESC % @/G` | C | |

### Functions using CSI, ordered by the final character(s)

| Sequence | | Notes |
|---|---|---|
| `@` ICH, `P` DCH, `X` ECH, `L` IL, `M` DL | S | |
| `A` CUU, `B` CUD, `C` CUF, `D` CUB, `E` CNL, `F` CPL, `G` CHA, `H` CUP, `f` HVP, `d` VPA, `` ` `` HPA, `a` HPR, `e` VPR | S | |
| `I` CHT, `Z` CBT, `g` TBC (0 and 3) | S | |
| `J` ED (0, 1, 2, 3), `K` EL (0, 1, 2) | S | 3 clears scrollback; `? J`, `? K` (selective erase) C |
| `S` SU, `T` SD | S | `T` with more than one parameter is mouse highlight tracking: C |
| `b` REP | S | |
| `m` SGR: 0-9, 21-25, 27-29, 30-39, 40-49, 90-97, 100-107, 38 and 48 in every form the census lists | S | 4:N, 53, 55, 58, 59 as the draft's D1, D2, D7 |
| `r` DECSTBM | S | |
| `s` SCOSC, `u` SCORC | S | `s` with parameters is a margin setting: C |
| `h`, `l` with 4 (IRM), 20 (LNM) | S | others C |
| `? h`, `? l` with 1, 6, 7, 12, 25, 47, 66, 1000, 1002, 1003, 1004, 1006, 1007, 1047, 1048, 1049, 2004, 2026 | S | 9, 1005, 1015, 1016 (old mouse encodings), 3, 4, 5, 8, 45, 69, 1034 and every other C |
| `SP q` DECSCUSR 0-6 | S | |
| `! p` DECSTR | S | |
| `c` DA1, `> c` DA2, `n` DSR 5 and 6, `? 6 n`, `$ p` and `? $ p` DECRQM, `> q` XTVERSION | A | DA3 (`= c`) C |
| `t` window operations | C | all of them; 14, 18 and 19 (size reports) are a W2 question, since the size is the pane's |
| `i` media copy, `$`-rectangle operations, `" q` DECSCA, `x` DECREQTPARM, every other final | C | |

### Operating System Commands

| Sequence | | Notes |
|---|---|---|
| OSC 0, 2 | S | the pane's title; BEL or ST ends it |
| OSC 1 | C | icon name |
| OSC 52 | S | an event carrying the text; a read request (`?`) is never answered |
| OSC 7 | S | the working directory, kept for the saved layout; not in the reference at this version, so a written row |
| OSC 4, 10, 11, 12, 104, 110, 111, 112 and every other | C | colour queries are not answered in v1: a program that asks (yew asks OSC 11) must time out as it does on a terminal that stays silent |

### Device-Control, Application Program-Command functions

DCS, APC, PM and SOS strings are consumed whole to ST. None is served in v1
(DECRQSS, XTGETTCAP and sixel included).

### Mouse Tracking, Bracketed Paste Mode, The Alternate Screen Buffer

The modes are stored and reported; what they make the terminal *send* is
the server's key and mouse encoder, which is W2's (the document's sections
"Mouse Tracking", "Bracketed Paste Mode", "PC-Style Function Keys").

### Expected gaps

1. **Reflow has no reference.** xterm does not reflow. The rows are
   properties and written expectations, with tmux as a second opinion on
   text.
2. **Scrollback cannot be read from the reference** except by growing the
   screen. Rows about what enters scrollback use that, and tmux.
3. **Seven named divergences** (the draft's D1 to D7) are compared with
   written expectations.
4. **Widths.** The first sweep against the reference will find code points
   where a table generated from Unicode data and the reference's C library
   disagree. I expect a few hundred, almost all in emoji and in recently
   added scripts, and none in the corpus.
5. **The census has not asked everything.** Not yet measured: DEL inside a
   sequence, the exact parameter cap, VT and FF, SCOSC and SCORC, the old
   mouse encodings' mode reports, a wide character at the last column with
   autowrap off when nothing is written after it, what enters scrollback
   under a partial region. W1's first commit extends the census with these.
6. **The checked machine's step budget.** Emulator tests over the corpus may
   pass the checked tier's budget and fall back to native, as other
   repositories have seen; the rows will say which tier ran each.

### Which of the PAX readiness answers change this

None changes the emulator's scope: the grid is the same on every host. They
change its neighbours, and the two drafts carry them:

| Question | If the answer is no | Changes |
|---|---|---|
| Does the console draw wide and combining characters? (answered: one cell per code point) | | W2's renderer places every character; W1 unchanged |
| How many colours? (answered: 16) | | W2's renderer downsamples; W1 keeps colours as set |
| Does Ctrl-Space arrive as 0x00? (answered: no, being fixed) | a second default prefix | W3 |
| Can the server wait on ptys, sockets and signals at once? (answered: not yet) | no W2 server | W2, blocking |
| Does a pty carry a megabyte in order, and how much does it queue? (answered: yes; 20480 bytes) | | W2's input queue and read size |
| Does the console answer DA1 and CPR? (answered: yes, and nothing else) | | W2's client must not wait on any other query there |
| Does a daemon outlive its login? (open) | detach does not survive logout on PAX | W2 on PAX, W6 |
| Is there a per-user runtime directory? (open) | fall back to `/tmp/warren-UID` | W2 |

## Decisions asked for, each with a recommendation

Each is stated where it is argued; this is the index.

| | Decision | Recommended | Where |
|---|---|---|---|
| R-wr00-1 | the reference emulator | xterm 390 from Ubuntu 24.04's package, read through two passes; tmux 3.4 as the second black box | `docs/SCREEN-DUMP.md` |
| R-wr00-2 | the document of record | the control-sequence text in the reference's own package (patch 390), beside the newer text PAX already cites | `docs/SOURCES.md` |
| R-wr00-3 | the dump's normalisations N1 to N5 | as listed | `docs/SCREEN-DUMP.md` |
| R-wr00-4 | divergences from the reference D1 to D7 | as listed | emulator draft, 3.1 |
| R-wr00-5 | W1 serves the DEC graphics set, REP, SU/SD, tab motions, DECRQM and mode 2026 beyond the decided subset | yes | emulator draft, 3.3 |
| R-wr00-6 | reflow on resize, by invariants R1 to R8; never on the alternate screen | yes | emulator draft, 4 |
| R-wr00-7 | scrollback stored by line, capped in its own bytes, default 8 MiB | yes | emulator draft, 6 |
| R-wr00-8 | the width table's Unicode version follows the reference's C library | yes | emulator draft, 5 |
| R-wr00-9 | `TERM=xterm-256color`, `COLORTERM=truecolor`, no terminfo entry of warren's own in v1 | yes | `docs/TERM.md` |
| R-wr00-10 | the socket's place and the refusal of an open directory | `$XDG_RUNTIME_DIR/warren/default`, else `/tmp/warren-UID/default` | survey, 1 |
| R-wr00-11 | v1 clients of a session are mirrored; a too-small client is attached but not counted | yes | survey, 2 and 11 |
| R-wr00-12 | frames carry cells, keys travel as events, frames are acknowledged, bindings live on the server | yes | protocol draft, 7 |
| R-wr00-13 | the server signals no process; a pane ends by its master being closed | yes | protocol draft, N1 |
| R-wr00-14 | OSC 52 is write-only, and off by default for programs inside | yes | survey, 7 |
| R-wr00-15 | herdr is the project at `herdrdev/herdr`, surveyed at 0.9.5 from its documents | yes | `docs/SOURCES.md` |
| R-wr00-16 | den has no pager; its corpus row is long plain output over a synthetic history | yes | corpus |
| R-wr00-17 | `infocmp`'s output counts as a black-box run, not as reading ncurses | to confirm | `docs/TERM.md` |
| R-wr00-18 | a unified wait in wolf-std is W2's blocking dependency; peer credentials and a start lock are wanted | launch it | protocol draft, 5 |

## Forbidden, and what was read

Nothing on the never-read list was opened. The reference emulator and tmux
ran only as binaries. zellij and herdr were not run. `docs/SOURCES.md` lists
every document with its digest. One judgement call is recorded there: the
terminfo entries were read through `infocmp`, a binary, and the reference
package's own `xterm.terminfo` file was left unopened.

## Evidence index

| What | Where |
|---|---|
| the harness cases and their expectations (three written by hand first) | `tests/vt/cases.py`, `tests/vt/expected/` |
| the census: 151 streams, their dumps' digests, and a readable summary | `tests/vt/census.py`, `census.sha256`, `census.txt` |
| the fuzz generator's streams and their dumps, by digest | `tests/corpus/fuzz.sha256`, `fuzz-screens.sha256` |
| five recordings, their scripts, and their dumps' digests | `tests/corpus/` |
| the oracle image's pins | `warren-oracle.toml`, `ci/packages.txt`, `ci/oracle-binaries.lock` |
| the session rows against tmux | `tools/session/tmux_rows.py` |

## Seen red

| Row | When | What it showed |
|---|---|---|
| `mode` on all three hand-written cases | the first take | mode 1048 always answers "set": my expectation was wrong, and the mode is not state |
| `oracle-run scroll`: print screen wrote 5 rows for 24 | the first take | print screen prints only the scroll region unless `printerExtent` is set |
| `oracle-run modes`: CPR and DECCIR disagree | the first take | CPR is relative under origin mode; the per-cell requests are too |
| the first census, rows after a bold cell | reading the dumps | print screen does not reset before a plain cell; the marker passes inherited it; the spread pass replaced them |
| `oracle-run` on 9 of 32 fuzz seeds | the first fuzz take | spreading in place disturbed wide characters not yet copied; copies now land on fresh columns |
| `oracle-run` on 8 of 32 fuzz seeds | the second | my model of print screen's rule was wrong; the check now holds only what pass A states outright |
| `tmux-screen pending-wrap` | the first tmux take | tmux reports a pending wrap as column 81; normalisation T1 |
| the scaffold's Linux job on `trunk` | the push | the workflow called `tools/in-container` before the file existed; this branch adds it |

## Not measured

- Nothing on PAX.
- zellij and herdr as running programs.
- The reference's inactive screen, its scrollback, and its character-set
  state, which the mechanism cannot show.
- macOS has no oracle rows: the reference emulator runs in the Linux image
  only. macOS runs the unit gate, the build and the tests.
- Whether the recordings replay to the same screen on a different emulator
  version: the pins exist so that the question does not arise by accident.

## Done-when

- [x] the scaffold on `trunk`; this branch through a pull request
- [x] the oracle image pinned by base digest, snapshot instant, package list and binary digests
- [x] a headless, deterministic, cell-for-cell dump, with what it cannot show written down
- [x] the three mutation rows red by name
- [x] the survey, one table per subject
- [x] the corpus and the seeded generator, by digest
- [x] the `TERM` recommendation
- [x] W1's scope predicted before any emulator code
- [x] the two drafts
