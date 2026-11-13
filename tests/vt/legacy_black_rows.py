#!/usr/bin/env python3
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/vt'))
from legacy_black_fixture import repair


def main():
    assert repair(b'plain')==(b'plain',[])
    fixed,edits=repair(b'\x1b[1;4;30mm')
    assert fixed==b'\x1b[1;4;38;5;0mm' and len(edits)==1
    fixed,edits=repair(b'\x1b[30m\x1b[1mm')
    assert fixed==b'\x1b[38;5;0m\x1b[1mm' and len(edits)==1
    for data in (b'\x1b[38;5;30m',b'\x1b[48;2;30;30;30m',b'\x1b[90m',b'\x1b[31m'):
        assert repair(data)==(data,[])
    for data in (b'\x1b[38;5m',b'\x1b[30:1m'):
        try:repair(data)
        except ValueError:pass
        else:raise AssertionError('unsupported owned form accepted')
    print('PASS D13 source-repair legacy30-only colour-arguments-preserved order-independent no-injection controls-unchanged')


if __name__=='__main__':main()
