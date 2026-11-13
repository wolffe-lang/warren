#!/usr/bin/env python3
"""The fresh drive uses the owned generator and refuses oversized work."""
from pathlib import Path
import hashlib
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
sys.path.insert(0, str(ROOT / 'tools/corpus'))
from fresh_fuzz import generated
import fuzz


def main():
    cases = generated(200, 4096)
    assert len(cases) == 200 and list(cases)[0] == 'fresh-0001' and list(cases)[-1] == 'fresh-0200'
    for seed, (name, data) in enumerate(cases.items(), 1):
        assert name == 'fresh-%04d' % seed and data == fuzz.stream(seed, 4096)
        assert len(data) >= 4096
    assert generated(2, 1024) == generated(2, 1024)
    assert len(generated(5000, 64)) == 5000
    for count, size in ((0, 4096), (5001, 4096), (200, 0), (1, 65537)):
        try:
            generated(count, size)
        except ValueError:
            pass
        else:
            raise AssertionError(('unbounded drive accepted', count, size))
    print('PASS fresh-fuzz generator=owned exact-count=200 minimum-bytes=4096 nightly-count=5000 bounded-refusals')


if __name__ == '__main__':
    main()
