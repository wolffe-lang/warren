#!/usr/bin/env python3
"""Prove assigned scalar expansion and malformed-range refusal."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
assigned = runpy.run_path(str(ROOT / 'tools/vt/generate_assigned.py'))['assigned']


def row(code, name, category):
    return ';'.join([code, name, category] + [''] * 12)


def main():
    data = '\n'.join([
        row('0000', '<control>', 'Cc'),
        row('0041', 'A', 'Lu'), row('0042', 'B', 'Lu'),
        row('3400', '<CJK Ideograph Extension A, First>', 'Lo'),
        row('3402', '<CJK Ideograph Extension A, Last>', 'Lo'),
        row('D800', '<Non Private Use High Surrogate, First>', 'Cs'),
        row('D801', '<Non Private Use High Surrogate, Last>', 'Cs'),
        row('E000', '<private-use>', 'Co'),
    ]).encode()
    got = assigned(data)
    assert got['assigned_scalars'] == 7, got
    assert got['excluded_non_scalars'] == 2
    assert got['ranges'] == [[0, 0, 'Cc'], [65, 66, 'Lu'], [0x3400, 0x3402, 'Lo'], [0xE000, 0xE000, 'Co']]
    assert got['counts'] == {'Cc': 1, 'Lu': 2, 'Lo': 3, 'Co': 1}
    bad = [b'not-a-UnicodeData-row', row('3400', '<CJK, First>', 'Lo').encode(),
           row('3401', '<CJK, Last>', 'Lo').encode(),
           (row('0042', 'B', 'Lu') + '\n' + row('0041', 'A', 'Lu')).encode(),
           (row('3400', '<CJK, First>', 'Lo') + '\n' + row('3402', '<OTHER, Last>', 'Lo')).encode(),
           row('110000', 'outside', 'Lo').encode()]
    for value in bad:
        try:
            assigned(value)
        except ValueError:
            pass
        else:
            raise AssertionError('malformed normative data accepted: %r' % value)
    print('PASS assigned scalar expansion categories surrogate-exclusion malformed-refusal')


if __name__ == '__main__':
    main()
