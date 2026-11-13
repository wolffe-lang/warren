#!/usr/bin/env python3
"""The replacement width rule matches all350 measured C-library exceptions."""
from bisect import bisect_right
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[2]


def main():
    path=ROOT/'tests/vt/width-exceptions.json';policy=json.loads(path.read_text())
    metadata=json.loads((ROOT/'tests/vt/width-ranges.json').read_text());ranges=metadata['ranges'];starts=[row[0] for row in ranges]
    seen=set()
    for group in policy['groups']:
        count=0;assert group['reason'] and group['width'] in (0,1,2)
        for low,high in group['ranges']:
            for cp in range(int(low,16),int(high,16)+1):
                at=bisect_right(starts,cp)-1
                width=ranges[at][2] if at>=0 and cp<=ranges[at][1] else 1
                assert width==group['width'],(group['name'],'U+%04X'%cp,width,group['width'])
                assert cp not in seen;seen.add(cp);count+=1
        assert count==group['count']
    assert len(seen)==policy['total']==350
    assert metadata['exceptions_sha256']==hashlib.sha256(path.read_bytes()).hexdigest()
    print('PASS width-exceptions exact350 ranges counts reason metadata-binding matches-C-library')


if __name__=='__main__':main()
