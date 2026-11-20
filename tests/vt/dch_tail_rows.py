#!/usr/bin/env python3
"""D15: the source trace finds a DCH whose vacated span starts on a wide
character's second half; the split reference input avoids it; the paired bound
permits exactly the one cell the reference blanks and refuses anything else.

The reference, deleting n characters at column c while cells move left, blanks
column cols-n afterwards if column cols-n+1 held a second half before the
shift: it erases the cell that moved there from the last column. warren keeps
that cell. These rows are source and frame data only; they run no terminal.
"""
import copy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tests/vt', 'tools/vt'):
    sys.path.insert(0, str(ROOT / part))
from expectations import blank, text_row  # noqa: E402

C = b'\x1b['
WIDE = '中'.encode()
FAILED = []


def row(name, check):
    try:
        check()
    except Exception as error:  # a missing piece is a red row, by name
        print('FAIL dch-tail %s: %s: %s' % (name, type(error).__name__, str(error)[:300]), flush=True)
        FAILED.append(name)
    else:
        print('PASS dch-tail %s' % name, flush=True)


def triggers(data, cols, rows=4):
    from erase_extent_fixture import trace
    return trace(data, cols, rows)['dch_tail']


def one(data, cols, count, col, screen=0, observable=True, rows=4):
    found = triggers(data, cols, rows)
    assert len(found) == 1, found
    t = found[0]
    assert (t['count'], t['row'], t['col'], t['screen'], t['observable']) == (count, 1, col, screen, observable), t
    assert data[t['offset']:t['end']] == C + b'%dP' % count, (data[t['offset']:t['end']], t)
    return t


# Measured shapes (10 columns unless said). Each deletes at column 1 unless said.
Z2 = C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'41m' + C + b'1;1H' + C + b'7P'
Z3 = C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;2H' + C + b'6P'
Z4 = C + b'1;4H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'6P'
Z7 = C + b'?1049h' + C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'7P'
Z8 = C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'8P'
Z11 = C + b'1;1Habc' + WIDE + b'efgQR' + C + b'1;1H' + C + b'6P'
MOVED = b'abcdef' + WIDE + C + b'1;12HQ' + C + b'44m' + C + b'1;1H' + C + b'5P'      # 12 columns
NOTHING_MOVES = C + b'1;3H' + WIDE + C + b'1;4H' + C + b'7P'
ICH = C + b'1;3H' + WIDE + C + b'1;10HQ' + C + b'1;1H' + C + b'3@'
LAST_PAIR = C + b'1;9H' + WIDE + C + b'1;1H' + C + b'P'
Z1 = C + b'1;45H' + WIDE + C + b'1;79H' + 'あ'.encode() + C + b'1;1H' + C + b'35P'  # 80 columns


def trace_rows():
    row('trace-pair-deleted', lambda: one(Z2, 10, 7, 3))
    row('trace-lead-four', lambda: one(Z4, 10, 6, 4))
    row('trace-written-last-column', lambda: one(Z11, 10, 6, 4))
    row('trace-pair-moves', lambda: one(MOVED, 12, 5, 7))
    row('trace-alternate-screen', lambda: one(Z7, 10, 7, 3, screen=1))
    row('trace-second-half-moves-in', lambda: one(Z1, 80, 35, 45, observable=False, rows=24))
    row('trace-one-deleted-last-pair', lambda: one(LAST_PAIR, 10, 1, 9, observable=False))

    def none(data, cols=10):
        assert triggers(data, cols) == [], triggers(data, cols)
    row('trace-control-blank-at-boundary', lambda: none(Z3))
    row('trace-control-first-half-at-boundary', lambda: none(Z8))
    row('trace-control-nothing-moves', lambda: none(NOTHING_MOVES))
    row('trace-control-insert', lambda: none(ICH))
    row('trace-control-narrow-only', lambda: none(C + b'1;10HQ' + C + b'1;1H' + C + b'7P'))


def split_rows():
    def split_pair_deleted():
        from dch_tail_fixture import repair
        fixed, edits = repair(Z2, 10, 4)
        assert fixed == Z2[:-len(C + b'7P')] + C + b'6P' + C + b'P', fixed
        assert len(edits) == 1 and edits[0]['original_hex'] == (C + b'7P').hex(), edits
        assert edits[0]['replacement_hex'] == (C + b'6P' + C + b'P').hex() and edits[0]['offset'] == len(Z2) - 4
        assert triggers(fixed, 10) == []
    row('split-pair-deleted', split_pair_deleted)

    def split_every_shape():
        from dch_tail_fixture import repair
        from erase_extent_fixture import trace
        for data, cols in ((Z4, 10), (Z11, 10), (MOVED, 12), (Z7, 10), (Z2 + Z4, 10)):
            fixed, edits = repair(data, cols, 4)
            assert edits and fixed != data, data
            assert trace(fixed, cols, 4)['dch_tail'] == [], data
            assert trace(fixed, cols, 4)['cursor'] == trace(data, cols, 4)['cursor'], data
    row('split-every-shape-meets-no-trigger', split_every_shape)

    def split_leaves_the_rest():
        from dch_tail_fixture import repair
        for data, cols, rows in ((Z3, 10, 4), (Z8, 10, 4), (NOTHING_MOVES, 10, 4), (ICH, 10, 4),
                                 (LAST_PAIR, 10, 4), (Z1, 80, 24), (b'plain', 10, 4)):
            assert repair(data, cols, rows) == (data, []), data
    row('split-controls-and-unobservable-unchanged', split_leaves_the_rest)


def frames(cols=10):
    """The reference's Z2 frame and its split twin: Q kept, or blanked with the red pen."""
    original = blank(cols, 4)
    original['rows'][0][2] = [1, 'U+0020', 'bg=idx:1']
    original['extents'][0] = 0
    repaired = copy.deepcopy(original)
    repaired['rows'][0][2] = [1, 'U+0051', '-']
    repaired['extents'][0] = 3
    return original, repaired


def refuses(function):
    try:
        function()
    except (AssertionError, ValueError):
        return
    raise AssertionError('D15 bound accepted a planted difference')


def bound_rows():
    def accepts():
        from fresh_expectations import dch_pair
        original, repaired = frames()
        expected, detail = dch_pair(Z2, original, repaired)
        assert expected == repaired, expected
        assert detail['cells'] == [[1, 3, [1, 'U+0020', 'bg=idx:1'], [1, 'U+0051', '-']]], detail
        assert len(detail['triggers']) == 1 and detail['edits'], detail
        same, detail = dch_pair(Z2, original, copy.deepcopy(original))
        assert same == original and detail['cells'] == []
    row('bound-accepts-the-blanked-cell', accepts)

    def refusals():
        from fresh_expectations import dch_pair
        original, repaired = frames()
        refuses(lambda: dch_pair(b'Q', original, repaired))                 # no trigger
        refuses(lambda: dch_pair(LAST_PAIR, original, repaired))            # an unobservable trigger only
        written = copy.deepcopy(original)
        written['rows'][0][2] = [1, 'U+0058', '-']
        written['extents'][0] = 3
        refuses(lambda: dch_pair(Z2, written, repaired))                    # the reference cell was not a blank
        wide = copy.deepcopy(repaired)
        wide['rows'][0][2] = [2, 'U+4E2D', '-']
        refuses(lambda: dch_pair(Z2, original, wide))                       # a width changed
        second = copy.deepcopy(repaired)
        second['rows'][1][0] = [1, 'U+0051', '-']
        second['extents'][1] = 1
        refuses(lambda: dch_pair(Z2, original, second))                     # more cells than triggers
        cursor = copy.deepcopy(repaired)
        cursor['cursor']['col'] = 2
        refuses(lambda: dch_pair(Z2, original, cursor))                     # another field
        extent = copy.deepcopy(repaired)
        extent['extents'][0] = 5
        refuses(lambda: dch_pair(Z2, original, extent))                     # an extent past the cell
    row('bound-refuses-outside-the-cell', refusals)


def main():
    trace_rows()
    split_rows()
    bound_rows()
    if FAILED:
        print('FAIL dch-tail rows: %s' % ' '.join(FAILED), flush=True)
        return 1
    print('PASS dch-tail trace-triggers controls split-neutral bound-one-cell refusals', flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
