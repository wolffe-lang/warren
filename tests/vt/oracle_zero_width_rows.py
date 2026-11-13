#!/usr/bin/env python3
"""Decode measured zero-width jamo/Egyptian print clusters, not all Cf/Lo."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle


def main():
    attached = ((0x1160, 0x11FF), (0xD7B0, 0xD7C6),
                (0xD7CB, 0xD7FB), (0x13430, 0x1343F))
    count = 0
    for low, high in attached:
        for cp in range(low, high + 1):
            count += 1
            clusters = oracle.parse_print(('a' + chr(cp) + '\r\n').encode(), 1)[0]
            assert clusters == [[[0x61, cp], '-', False]], ('attached-print-cluster', hex(cp), clusters)
            assert oracle.lay_out(clusters, ['FF9F', 'FFE0'], 2) == [
                [1, 'U+0061+U+%04X' % cp, '-', False]]
    assert count == 248
    # These are not observed attached scalar classes. In particular FFF9 is
    # omitted by the pinned reference printer, not evidence to absorb all Cf.
    for cp in (0x115F, 0x1200, 0xD7AF, 0xD7C7, 0xD7CA, 0xD7FC,
               0xFFF9, 0xFFFA, 0xFFFB, 0x1342F, 0x13440, 0x200D):
        assert not oracle.is_combining(cp), ('nontrigger-cluster-class', hex(cp))
    base = oracle.parse_print('aᅠ\r\n'.encode(), 1)[0]
    try:
        oracle.lay_out(base, ['FF9E', 'FFE0'], 2)
    except oracle.OracleError:
        pass
    else:
        raise AssertionError('wrong checksum accepted')
    assert oracle.is_combining(0x301)
    print('PASS oracle-zero-width-clusters attached248 strict-adjacent-and-Cf-controls checksum-refusal')


if __name__ == '__main__':
    main()
