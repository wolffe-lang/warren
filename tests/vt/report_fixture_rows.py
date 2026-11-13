#!/usr/bin/env python3
"""Report fixtures preserve colour arguments and use measured cursor positions."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/vt'))
from report_fixture import without_bold, tab_operations, column_one


def main():
    plain=b'plain'
    assert without_bold(plain)==(plain,[])
    fixed, edits=without_bold(b'A\x1b[1mB\x1b[1;4;31mC\x1b[22m')
    assert fixed==b'AB\x1b[4;31mC\x1b[22m' and len(edits)==2
    colors=b'\x1b[38;5;1;48;2;1;1;1m'
    assert without_bold(colors)==(colors,[])
    fixed,_=without_bold(b'\x1b[1;38;2;1;1;1;1mX')
    assert fixed==b'\x1b[38;2;1;1;1mX'
    fixed,_=without_bold(b'\x1b[1;;1m')
    assert fixed==b'\x1b[0m'
    for invalid in (b'\x1b[1;38;5m',b'\x1b[1;48;2;1m',b'\x1b[1:2m'):
        try: without_bold(invalid)
        except ValueError: pass
        else: raise AssertionError('unsupported colour/SGR accepted')
    data=b'\x1bHxx\x1b[g\x1b[3g'
    ops=tab_operations(data)
    assert [entry['kind'] for entry in ops]==['set','clear-current','clear-all']
    assert column_one(ops[:1],[1])
    assert column_one(ops[:2],[1,25])
    assert not column_one(ops[:2],[1,1])
    assert not column_one(ops,[1,25,2])
    assert not column_one([],[])
    assert tab_operations(b'\x1bc')[0]['kind']=='clear-all'
    try: column_one(ops,[1])
    except ValueError: pass
    else: raise AssertionError('missing measured positions accepted')
    print('PASS report-fixtures no-bold-only colour-arguments-preserved no-implicit-reset tab-one-from-measured-positions no-candidate-output')


if __name__=='__main__': main()
