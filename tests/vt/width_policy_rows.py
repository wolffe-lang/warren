#!/usr/bin/env python3
"""The exhaustive sweep permits zero non-control differences; D11 is history."""
from pathlib import Path
import copy,hashlib,json,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/vt'))
from check_width_policy import expected_differences,validate


def main():
    assert expected_differences()==[], 'withdrawn D11 is not a live mismatch allowance'
    result={'unicode':'15.1.0','measured_scalars':287346,'excluded_non_scalars':2048,
        'classifications':{'control':65,'equal':287281},'disagreements':[],
        'controls':[{'scalar':'U+%04X'%cp,'category':'Cc','classification':'control'} for cp in [*range(32),*range(127,160)]],
        'assigned_sha256':hashlib.sha256((ROOT/'tests/vt/assigned-ranges.json').read_bytes()).hexdigest(),
        'widths_sha256':hashlib.sha256((ROOT/'tests/vt/width-ranges.json').read_bytes()).hexdigest()}
    validate(result)
    bad={'scalar':'U+0041','category':'Lu','expected':1,'row':1,'col':4,'classification':'native-1-reference-2'}
    plants=[]
    first=copy.deepcopy(result);first['disagreements']=[bad];plants.append(first)
    historic=json.loads((ROOT/'tests/vt/width-divergences.json').read_text())
    old=[]
    for group in historic['groups']:
        for low,high in group['ranges']:
            for cp in range(int(low,16),int(high,16)+1):old.append({**bad,'scalar':'U+%04X'%cp})
    assert len(old)==350
    extra=copy.deepcopy(result);extra['disagreements']=old+[bad];plants.append(extra)
    missing=copy.deepcopy(result);missing['measured_scalars']-=1;plants.append(missing)
    duplicate=copy.deepcopy(result);duplicate['disagreements']=[bad,bad];plants.append(duplicate)
    for changed in plants:
        try:validate(changed)
        except (AssertionError,ValueError):pass
        else:raise AssertionError('unapproved width difference accepted')
    print('PASS widths zero-differences first-red historical350-plus351st-red missing-red duplicate-red')


if __name__=='__main__':main()
