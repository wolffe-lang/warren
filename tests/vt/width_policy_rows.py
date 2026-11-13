#!/usr/bin/env python3
"""D11 is an exact exhaustive set, never an allowance for arbitrary mismatch."""
from pathlib import Path
from collections import Counter
import copy,hashlib,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/vt'))
from check_width_policy import expected_differences, validate


def main():
    differences=expected_differences()
    assert len(differences)==350
    categories=Counter(row['classification'] for row in differences)
    categories.update({'control':65,'equal':286931})
    result={'unicode':'15.1.0','measured_scalars':287346,'excluded_non_scalars':2048,
        'classifications':dict(categories),'disagreements':differences,
        'controls':[{'scalar':'U+%04X'%cp,'category':'Cc','classification':'control'} for cp in [*range(32),*range(127,160)]],
        'assigned_sha256':hashlib.sha256((ROOT/'tests/vt/assigned-ranges.json').read_bytes()).hexdigest(),
        'widths_sha256':hashlib.sha256((ROOT/'tests/vt/width-ranges.json').read_bytes()).hexdigest()}
    validate(result)
    plants=[]
    extra=copy.deepcopy(result)
    extra['disagreements'].append({'scalar':'U+0041','category':'Lu','expected':1,'row':1,'col':4,'classification':'native-1-reference-2'})
    plants.append(extra)
    missing=copy.deepcopy(result); missing['disagreements'].pop(); plants.append(missing)
    wrong=copy.deepcopy(result); wrong['disagreements'][0]['col']=2; plants.append(wrong)
    duplicate=copy.deepcopy(result); duplicate['disagreements'][0]=duplicate['disagreements'][1]; plants.append(duplicate)
    for changed in plants:
        try: validate(changed)
        except (AssertionError,ValueError): pass
        else: raise AssertionError('unapproved width difference accepted')
    print('PASS D11 exact350 extra351-red missing-red wrong-width-red duplicate-red')


if __name__=='__main__': main()
