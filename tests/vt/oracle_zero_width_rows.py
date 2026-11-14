#!/usr/bin/env python3
"""Decode pinned Unicode15.1 classes, not the host Python's Unicode version."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle


def main():
    pins = json.loads((ROOT / 'tests/vt/unicode-sources.json').read_text())
    assigned = json.loads((ROOT / 'tests/vt/assigned-ranges.json').read_text())
    exceptions = json.loads((ROOT / 'tests/vt/width-exceptions.json').read_text())
    normal = json.loads((ROOT / 'tests/vt/combining-ranges.json').read_text())
    assert pins['version'] == assigned['version'] == exceptions['unicode'] == normal['version'] == '15.1.0'
    assert normal['source_sha256'] == assigned['source_sha256']
    assert assigned['source_sha256'] == next(source['sha256'] for source in pins['sources'] if source['name'] == 'UnicodeData.txt')

    def category(cp):
        return next((kind for low, high, kind in assigned['ranges'] if low <= cp <= high), 'Cn')

    attached = set()
    for group in exceptions['groups']:
        if group['width'] == 0:
            for low, high in group['ranges']:
                attached.update(range(int(low, 16), int(high, 16) + 1))
    attached.difference_update(range(0xFFF9, 0xFFFC))  # Observed annotation controls are omitted.
    assert len(attached) == 248
    for cp in sorted(attached):
        assert category(cp) in ('Lo', 'Cf')
        clusters = oracle.parse_print(('a' + chr(cp) + '\r\n').encode(), 1)[0]
        assert clusters == [[[0x61, cp], '-', False]], ('attached-print-cluster', hex(cp), clusters)
        assert oracle.lay_out(clusters, ['FF9F', 'FFE0'], 2) == [
            [1, 'U+0061+U+%04X' % cp, '-', False]]
    # Outside the exception classes, expectations come from the pinned category
    # data too. U13440 is Mn in15.1, not the Cn of Python3.11's Unicode14 data.
    for cp in (0x115F, 0x1200, 0xD7AF, 0xD7C7, 0xD7CA, 0xD7FC,
               0xFFF9, 0xFFFA, 0xFFFB, 0x1342F, 0x13440, 0x13441, 0x200D, 0x301):
        expected = any(low <= cp <= high for low, high in normal['ranges'])
        assert expected == (category(cp) in ('Mn', 'Me')), ('covered-control-category', hex(cp))
        assert oracle.is_combining(cp) == expected, ('pinned-nonexception-class', hex(cp), category(cp))
    assert category(0x13440) == 'Mn' and oracle.is_combining(0x13440)
    clusters = oracle.parse_print('a\U00013440\r\n'.encode(), 1)[0]
    assert clusters == [[[0x61, 0x13440], '-', False]]
    base = oracle.parse_print('aᅠ\r\n'.encode(), 1)[0]
    try:
        oracle.lay_out(base, ['FF9E', 'FFE0'], 2)
    except oracle.OracleError:
        pass
    else:
        raise AssertionError('wrong checksum accepted')
    print('PASS oracle-zero-width-clusters pinned-unicode=15.1.0 attached248 U13440=Mn host-unicodedata=unused checksum-refusal')


if __name__ == '__main__':
    main()
