#!/usr/bin/env python3
"""Only the open RI→HT→mark interaction may exclude a reference comparison."""
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from erase_extent_fixture import trace
C = b'\x1b['
RI = b'\x1bM'
MARK = '́'.encode()


def exclusions(data):
    return trace(data)['reference_exclusions']


def main():
    assert len(exclusions(b'abcd' + RI + b'\t' + MARK)) == 1
    assert len(exclusions(b'abcd' + RI + C + b'31m\t' + MARK)) == 1
    assert len(exclusions(b'abcd' + RI + b'\t\x1b7' + MARK)) == 1
    assert len(exclusions(b'abcd' + RI + b'\t' + C + b'S' + MARK)) == 1
    for tail in (b'a' + MARK, C + b'1;9H' + MARK, b'\r' + MARK,
                 b'\x1bD' + MARK, b'\x1b8' + MARK, C + b'X' + MARK):
        assert not exclusions(b'abcd' + RI + b'\t' + tail)
    assert not exclusions(b'abcd' + RI + MARK)
    assert not exclusions(b'abcd\t' + MARK)
    stream = runpy.run_path(str(ROOT / 'tools/corpus/fuzz.py'))['stream']
    selected = [seed for seed in range(1, 201) if exclusions(stream(seed, 4096))]
    assert selected == [], selected
    print('PASS RI-HT-mark exclusion exact-pattern source-only cases0-of200 clear-and-new-graphic-refusals')


if __name__ == '__main__':
    main()
