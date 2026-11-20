"""D15's frozen cases (tests/vt/reference/d15): the inputs and warren's frames.

Each trigger case deletes characters while cells move left, with the vacated
span starting on a wide character's second half. The reference blanks the cell
that moved in from the last column; its split input (tools/vt/dch_tail_fixture)
keeps it. The written frame is warren's contract for both inputs, written here
by hand: it must equal the reference's frame for the split input, and differ
from the reference's frame for the original input in the one bounded cell. The
controls meet no trigger, are not split, and expect the reference's own frame.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tools/vt', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
from dch_tail_fixture import repair  # noqa: E402
from expectations import blank  # noqa: E402

E = b'\x1b'
C = E + b'['
HEAD = E + b']2;t\x07' + C + b'2 q'
WIDE = '中'.encode()
ROWS = 4


def cell(char):
    return [1, 'U+%04X' % ord(char), '-']


def written(cols, cells, extent, vacated, pen='-', cursor=1, alternate=False):
    """Row 1 holds `cells` by column; the last `vacated` columns are blanks in the pen."""
    frame = blank(cols, ROWS)
    for col, value in cells.items():
        frame['rows'][0][col - 1] = value
    for col in range(cols - vacated + 1, cols + 1):
        frame['rows'][0][col - 1] = [1, 'U+0020', pen]
    frame['extents'][0] = extent
    frame['cursor']['col'] = cursor
    if alternate:
        frame['modes']['alternate-screen-1049'] = 1
    return frame


def definitions():
    trig = {
        # The pair deleted, the red pen: Q moves from 10 to 3.
        'pair-deleted': (10, C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'41m' + C + b'1;1H' + C + b'7P',
                         written(10, {3: cell('Q')}, 3, 7, 'bg=idx:1')),
        # A first half in column 4: Q moves from 10 to 4.
        'first-half-four': (10, C + b'1;4H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'6P',
                            written(10, {4: cell('Q')}, 4, 6)),
        # A written row: R moves from the last column to 4.
        'written-last-column': (10, C + b'1;1Habc' + WIDE + b'efgQR' + C + b'1;1H' + C + b'6P',
                                written(10, {1: cell('f'), 2: cell('g'), 3: cell('Q'), 4: cell('R')}, 4, 6)),
        # The pair itself moves (7-8 to 2-3) and Q moves from 12 to 7, the blue pen.
        'pair-moves': (12, b'abcdef' + WIDE + C + b'1;12HQ' + C + b'44m' + C + b'1;1H' + C + b'5P',
                       written(12, {1: cell('f'), 2: [2, 'U+4E2D', '-'], 3: [0, '-', '-'], 7: cell('Q')},
                               7, 5, 'bg=idx:4')),
        # The same on the alternate screen.
        'alternate-screen': (10, C + b'?1049h' + C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'7P',
                             written(10, {3: cell('Q')}, 3, 7, alternate=True)),
    }
    controls = {
        # A first half, not a second half, starts the vacated span.
        'first-half-at-boundary': (10, C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'8P'),
        # A blank starts the vacated span.
        'blank-at-boundary': (10, C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;2H' + C + b'6P'),
        # Nothing moves: the deletion reaches the last column from a second half.
        'nothing-moves': (10, C + b'1;3H' + WIDE + C + b'1;4H' + C + b'7P'),
    }
    result = {}
    for name, (cols, body, frame) in trig.items():
        original = HEAD + body
        split, edits = repair(original, cols, ROWS)
        assert edits and split != original, name
        result[name] = {'kind': 'trigger', 'size': [cols, ROWS], 'original': original, 'input': split,
                        'edits': edits, 'written': frame}
    for name, (cols, body) in controls.items():
        original = HEAD + body
        assert repair(original, cols, ROWS) == (original, []), name
        result[name] = {'kind': 'control', 'size': [cols, ROWS], 'original': original, 'input': original,
                        'edits': [], 'written': None}
    return result
