#!/usr/bin/env python3
"""Require zero assigned-scalar width differences outside the Cc controls.

The withdrawn D11 data remains a historical measurement, never an allowance.
"""
from bisect import bisect_right
import argparse,hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]


def historical_differences():
    policy=json.loads((ROOT/'tests/vt/width-divergences.json').read_text())
    ranges=json.loads((ROOT/'tests/vt/assigned-ranges.json').read_text())['ranges'];starts=[row[0] for row in ranges]
    result=[]
    for group in policy['groups']:
        count=0
        for low,high in group['ranges']:
            for cp in range(int(low,16),int(high,16)+1):
                first,last,category=ranges[bisect_right(starts,cp)-1];assert first<=cp<=last
                result.append({'scalar':'U+%04X'%cp,'category':category,'expected':group['native'],
                  'row':1,'col':group['reference']+2,'classification':'native-%d-reference-%d'%(group['native'],group['reference'])});count+=1
        assert count==group['count']
    assert len(result)==350 and len({row['scalar'] for row in result})==350
    return sorted(result,key=lambda row:int(row['scalar'][2:],16))


def exception_scalars():
    return [{**row,'historical_width':row['expected'],'expected':row['col']-2,'classification':'equal'} for row in historical_differences()]


def expected_differences():
    return []


def validate(result):
    policy=json.loads((ROOT/'tests/vt/width-exceptions.json').read_text())
    assert result['unicode']==policy['unicode']=='15.1.0'
    assert result['measured_scalars']==287346 and result['excluded_non_scalars']==2048
    for field,filename in (('assigned_sha256','assigned-ranges.json'),('widths_sha256','width-ranges.json')):
        assert result[field]==hashlib.sha256((ROOT/'tests/vt'/filename).read_bytes()).hexdigest()
    controls=result['controls'];assert len(controls)==65
    assert {row['scalar'] for row in controls}=={'U+%04X'%cp for cp in [*range(32),*range(127,160)]}
    assert all(row['category']=='Cc' and row['classification']=='control' for row in controls)
    assert result['disagreements']==[], 'any non-control width difference is red; D11 is withdrawn'
    assert result['classifications']=={'control':65,'equal':287281}
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('result',type=Path);a=p.parse_args()
    path=a.result/'result.json' if a.result.is_dir() else a.result;result=json.loads(path.read_text());validate(result)
    for filename in ('measurements.tsv','replies.bin'):
        assert hashlib.sha256((path.parent/filename).read_bytes()).hexdigest()==result[filename+'_sha256']
    print('PASS width-policy zero-noncontrol-differences measured287346 controls65 any-first-or-351st-red')


if __name__=='__main__':main()
