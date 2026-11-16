#!/usr/bin/env python3
"""D14 is source-only and bounded by the measured erase/scroll controls."""
from pathlib import Path
import copy
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from erase_extent_fixture import apply, trace
C = b'\x1b['


def main():
    matrix = runpy.run_path(str(ROOT / 'tests/vt/probes/erase_scroll_rows.py'))['cases']()
    reference = {'linefeed-scroll': 0, 'next-line-scroll': 0, 'scroll-up': 0,
                 'reverse-index-scroll': 0, 'scrolled-line-clear': 0,
                 'scrolled-written-prefix': 4, 'scrolled-move-away-back': 0,
                 'regional-linefeed-scroll': 0}
    for name, data in matrix.items():
        result = trace(data, 12, 4)
        expected = reference.get(name)
        if expected is None:
            assert result['rows'] == [], (name, result)
        else:
            assert len(result['rows']) == 1, (name, result)
            row = result['rows'][0]
            assert row['reference_extent'] == expected and row['contract_extent'] == 9, (name, result)
    assert trace(b'abcd' + C + b'5G' + C + b'5X', 12, 4)['events'] == []
    # An erase in display over a scroll-made row ends D14 for that row: the
    # reference extends a later erase there as on any row (warren#26). A line
    # clear (EL 2, above) does not.
    for label, clear in (('ED2', C + b'2J'), ('ED0-whole-row', C + b'4;1H' + C + b'0J'),
                         ('ED1-to-the-cursor', C + b'4;7H' + C + b'1J')):
        result = trace(C + b'4;1H\n' + clear + C + b'4;5H' + C + b'5X', 12, 4)
        assert result['rows'] == [], ('ED-ends-scroll-made', label, result)
    span = runpy.run_path(str(ROOT / 'tests/vt/probes/erase_span_bounds.py'))['cases']()
    for name, (data, replay) in span.items():
        if replay:
            continue
        result = trace(data, 12, 4)
        if name in ('print-after', 'background-first', 'background-last', 'changed-pen-background'):
            assert result['rows'] == [], (name, result)
        else:
            row, = result['rows']
            assert row['reference_extent'] == (4 if name == 'print-before' else 0), (name, result)
            assert row['contract_extent'] == (8 if 'trim-last' in name else 9), (name, result)
    frame = {'size': [12, 4], 'extents': [0, 0, 0, 0],
             'sentinel': {'cursor': [4, 5], 'unrelated-cell-field': 'unchanged'}}
    original = copy.deepcopy(frame)
    corrected, model = apply(matrix['linefeed-scroll'], frame)
    assert frame == original and corrected['sentinel'] == frame['sentinel']
    assert corrected['extents'] == [0, 0, 0, 9] and len(model['rows']) == 1
    wrong = copy.deepcopy(frame)
    wrong['extents'][3] = 1
    try:
        apply(matrix['linefeed-scroll'], wrong)
    except ValueError:
        pass
    else:
        raise AssertionError('D14 accepted a reference extent outside its source bound')
    assert apply(matrix['fresh-top'], frame)[0] == frame
    for data in (b'\x1b[', b'\x1b[48;2;4m', b'\x1b[?999h', b'\xff', b'a' * 65537):
        try:
            trace(data, 12, 4)
        except ValueError:
            pass
        else:
            raise AssertionError(('unowned input accepted', data[:20]))
    print('PASS D14 source-only scroll16 span10 no-trigger-row ED-ends-scroll-made strict-unsupported-input-refusal')


if __name__ == '__main__':
    main()
