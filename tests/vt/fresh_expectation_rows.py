#!/usr/bin/env python3
"""Each paired-reference fuzz rule refuses a difference just outside its bound."""
import copy
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tests/vt', 'tools/vt'):
    sys.path.insert(0, str(ROOT / part))
from expectations import blank, text_row
from fresh_expectations import background_pair, d9_triggers, legacy_pair
from report_expectations import recompose_no_bold
C = b'\x1b['


def refuses(function):
    try:
        function()
    except (AssertionError, ValueError):
        return
    raise AssertionError('paired-reference bound accepted a planted difference')


def main():
    original = blank(12, 4)
    text_row(original, 0, [88], 'bg=idx:4')
    repaired = copy.deepcopy(original)
    repaired['rows'][0][0][2] = '-'
    source = b'\x1b7' + C + b'44m\x1b8' + C + b'27mX'
    fixed, bounds = background_pair(source, original, repaired)
    assert bounds['cells'] == [[1, 1, 'bg=idx:4', None]] and fixed == repaired
    cursor = copy.deepcopy(repaired)
    cursor['cursor']['col'] = 3
    refuses(lambda: background_pair(source, original, cursor))
    refuses(lambda: background_pair(b'X', original, repaired))
    for foreground_setter in (b'31', b'91', b'38;5;9', b'38;2;1;2;3', b'39'):
        body = b'\x1b7' + C + b'48;5;181m\x1b8' + C + foreground_setter + b'm' + C + b'27mX'
        assert len(d9_triggers(body)) == 1, 'measured separate FG setter does not repair the BG cache'
    for background_setter in (b'42', b'102', b'48;5;9', b'48;2;1;2;3', b'49', b'0'):
        body = b'\x1b7' + C + b'48;5;181m\x1b8' + C + background_setter + b'm' + C + b'27mX'
        assert not d9_triggers(body), 'background setter/reset must disarm the stale BG trigger'
    black = blank(12, 4)
    text_row(black, 0, [88], 'bold,fg=idx:8')
    indexed = copy.deepcopy(black)
    indexed['rows'][0][0][2] = 'bold,fg=idx:0'
    fixed, bounds = legacy_pair(C + b'1;30mX', black, indexed)
    assert fixed == indexed and bounds['cells'] == [[1, 1, 'fg=idx:8', 'fg=idx:0']]
    refuses(lambda: legacy_pair(C + b'1;38;5;0mX', black, indexed))
    refuses(lambda: legacy_pair(C + b'1;30mX', indexed, black))
    wrong_cell = copy.deepcopy(indexed)
    wrong_cell['rows'][0][0][1] = 'U+0059'
    refuses(lambda: legacy_pair(C + b'1;30mX', black, wrong_cell))
    low = blank(12, 4)
    text_row(low, 0, [88], 'bold,fg=idx:1')
    high = copy.deepcopy(low)
    high['rows'][0][0][2] = 'fg=idx:9'
    assert recompose_no_bold('generic-fold', low, high)[1] == {(1, 1)}
    reverse = copy.deepcopy(low)
    reverse['rows'][0][0][2] = 'bold,fg=idx:9'
    reverse_plain = copy.deepcopy(reverse)
    reverse_plain['rows'][0][0][2] = 'fg=idx:1'
    refuses(lambda: recompose_no_bold('generic-opposite', reverse, reverse_plain))
    print('PASS fresh-reference-bounds D9-non-BG-refusal D13-source-and-opposite-refusal no-bold-opposite-refusal')


if __name__ == '__main__':
    main()
