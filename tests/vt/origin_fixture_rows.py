#!/usr/bin/env python3
"""D12 uses strict raw trigger guards and no candidate-derived metadata."""
from pathlib import Path
import copy,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/oracle')); import run as oracle
sys.path.insert(0,str(ROOT/'tests/vt'))
from origin_fixture import contract_screen
BASE=ROOT/'tests/vt/reference/origin/original'


def load(name):
    a=json.loads((BASE/name/'A.json').read_text()); a['print']=(BASE/name/'A.print').read_bytes(); return a


def main():
    a=load('dec-above-new-region'); before=copy.deepcopy(a)
    frame,note=contract_screen(a)
    assert frame['cursor']['row']==2 and frame['cursor']['col']==4 and frame['region']==[5,8]
    assert note['reference_cpr_row']==65534 and note['warren_cpr_row']==1
    assert a==before
    try: oracle.describe(a)
    except oracle.OracleError: pass
    else: raise AssertionError('original strict rejection was weakened')
    plants=[]
    off=copy.deepcopy(a); off['dec_modes']['6']='\x1b[?6;2$y'; plants.append(off)
    wrong=copy.deepcopy(a); wrong['cpr']='\x1b[65533;4R'; plants.append(wrong)
    col=copy.deepcopy(a); col['cpr']='\x1b[65534;7R'; plants.append(col)
    plants.append(load('dec-below-new-region'))
    for planted in plants:
        try: contract_screen(planted)
        except (AssertionError,ValueError,oracle.OracleError): pass
        else: raise AssertionError('D12 accepted a different trigger or changed report')
    print('PASS D12 exact-origin-above-top unsigned-wrap absolute-DECCIR no-mutation strict-original-rejection nontrigger-refusal')


if __name__=='__main__': main()
