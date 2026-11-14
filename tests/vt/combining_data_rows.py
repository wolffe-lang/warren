#!/usr/bin/env python3
"""Pinned print-cluster predicate: Mn/Me or a nonzero canonical combining class."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from generate_combining import combining


def row(cp, name, category, ccc):
    return ';'.join(['%04X' % cp, name, category, str(ccc)] + [''] * 11)


def main():
    data = '\n'.join([row(0x41, 'A', 'Lu', 0), row(0x300, 'M0', 'Mn', 0),
        row(0x301, 'M1', 'Mn', 230), row(0x488, 'ENCLOSING', 'Me', 0),
        row(0x903, 'SPACING', 'Mc', 0), row(0x1715, 'VIRAMA', 'Mc', 9),
        row(0x200D, 'JOINER', 'Cf', 0), row(0x13440, 'EGYPTIAN', 'Mn', 0)]).encode()
    result = combining(data)
    assert result == {'ranges': [[0x300, 0x301], [0x488, 0x488], [0x1715, 0x1715], [0x13440, 0x13440]], 'scalars': 5}
    ranged = (row(0x1000, '<Mark, First>', 'Mn', 0) + '\n' +
              row(0x1002, '<Mark, Last>', 'Mn', 0)).encode()
    assert combining(ranged) == {'ranges': [[0x1000, 0x1002]], 'scalars': 3}
    mismatch = (row(0x1000, '<Mark, First>', 'Mn', 0) + '\n' +
                row(0x1002, '<Mark, Last>', 'Mn', 230)).encode()
    try:
        combining(mismatch)
    except ValueError:
        pass
    else:
        raise AssertionError('mismatched First/Last combining class accepted')
    for bad in (row(0x301, 'BAD', 'Mn', -1), row(0x301, 'BAD', 'Mn', 256), row(0x301, 'BAD', 'Mn', 'x')):
        try:
            combining(bad.encode())
        except ValueError:
            pass
        else:
            raise AssertionError('malformed canonical combining class accepted')
    print('PASS combining-data Mn Me nonzero-CCC spacing-and-format-refusals malformed-CCC-refusals')


if __name__ == '__main__':
    main()
