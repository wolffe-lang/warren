#!/usr/bin/env python3
"""Eight dumps/16 passes: force row materialization without native data."""
import argparse,copy,hashlib,json,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle;import screen
sys.path.insert(0,str(ROOT/'tests/vt'));from origin_fixture import dump
sys.path.insert(0,str(ROOT/'tools/vt'));from repair_background_fixture import repair
C=b'\x1b['


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--minimized',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    selected={}
    for seed,col,amount in ((54,10,30),(175,66,12)):
        reduced=(a.minimized/('fresh-%04d/reduced.in'%seed)).read_bytes();op=C+str(amount).encode()+b'X';assert reduced.endswith(op)
        prefix=reduced[:-len(op)]
        selected['reduced-%04d-control'%seed]=(reduced,None)
        selected['reduced-%04d-line-clear'%seed]=(prefix+C+b'2K'+op,None)
        materialize=C+b'80G '+C+b'X'+C+str(col).encode()+b'G'
        selected['reduced-%04d-materialized'%seed]=(prefix+materialize+op,None)
    stream=runpy.run_path(str(ROOT/'tools/corpus/fuzz.py'))['stream']
    for seed,offset,col,amount,row,extent in ((54,4084,10,30,16,39),(175,3621,36,12,3,47)):
        data=stream(seed,4096);op=C+str(amount).encode()+b'X';assert data[offset:offset+len(op)]==op
        materialize=C+b'80G '+C+b'X'+C+str(col).encode()+b'G'
        fixed,events=repair(data[:offset]+materialize+data[offset:])
        selected['full-%04d-materialized'%seed]=(fixed,(seed,row,extent))
    assert len(selected)==8
    m={'schema':1,'dump_budget':8,'terminal_process_budget':16,'cases':{},'errors':[]}
    print('BUNDLE dumps-at-most=8 terminal-processes-at-most=16',flush=True)
    with oracle.Display() as display:
        for name,(data,bound) in selected.items():
            path=a.out/(name+'.in');path.write_bytes(data);work=a.out/name;entry={'input_sha256':hashlib.sha256(data).hexdigest()}
            try:
                got=dump(display,path.resolve(),80,24,work.resolve());raw=screen.dumps(got).encode();(work/'got.screen').write_bytes(raw);entry['screen_sha256']=hashlib.sha256(raw).hexdigest()
                if bound:
                    seed,row,extent=bound;original=screen.loads((a.baseline/('fresh-%04d/background-repaired-reference.screen'%seed)).read_text())
                    model=copy.deepcopy(original);model['extents'][row-1]=extent
                    entry['bound_differences']=screen.compare(model,got)
                    entry['requested_extent']=extent;entry['actual_extent']=got['extents'][row-1]
                print('MEASURE %s extents=%s bound=%s'%(name,got['extents'],entry.get('bound_differences','diagnostic-only')),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('MEASUREMENTS cases=8 errors=%d'%len(m['errors']),flush=True);return bool(m['errors'])


if __name__=='__main__':raise SystemExit(main())
