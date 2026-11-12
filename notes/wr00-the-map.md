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
