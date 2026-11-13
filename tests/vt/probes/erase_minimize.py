#!/usr/bin/env python3
"""Reference-only finite delta minimization: at most96 A passes per named red.

Owned complete generator pieces are removed, never split. The predicate is
only a partial ECH ending past the reference's reported extent. No candidate
program or expected candidate frame is used. Three final repeats are required.
"""
import argparse,hashlib,json,math,runpy,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle
sys.path.insert(0,str(ROOT/'tests/vt'));from origin_fixture import contract_screen
C=b'\x1b['


def pieces(seed,stop):
    f=runpy.run_path(str(ROOT/'tools/corpus/fuzz.py'));rng=f['Rng'](seed);out=[];total=0
    while total<stop:
        item=f['piece'](rng,80,24).encode();out.append(item);total+=len(item)
    assert total==stop
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    deadline=time.monotonic()+1800
    manifest={'schema':1,'terminal_process_budget':192,'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),'streams':{}}
    print('BUNDLE reference-A-only-at-most=192 seeds=54,175 cap-per-seed=96 final-repeats=3',flush=True)
    with oracle.Display() as display:
        for seed,stop,amount in ((54,4084,30),(175,3621,12)):
            directory=a.out/('fresh-%04d'%seed);directory.mkdir();calls=0;observations=[]
            def observe(items):
                nonlocal calls
                assert calls<96 and time.monotonic()<deadline
                data=b''.join(items)+C+str(amount).encode()+b'X';label='attempt-%03d'%calls;calls+=1
                work=directory/label;work.mkdir();source=work/'input.in';source.write_bytes(data)
                record={'attempt':label,'input_sha256':hashlib.sha256(data).hexdigest(),'bytes':len(data),'pieces':len(items)}
                try:
                    raw=oracle.run_pass(display,'A',source.resolve(),80,24,work.resolve())
                    try:frame=oracle.describe(raw)
                    except oracle.OracleError:frame,note=contract_screen(raw)
                    row,col=frame['cursor']['row'],frame['cursor']['col'];end=col+amount-1
                    mismatch=end<80 and frame['extents'][row-1]<end
                    record.update(mismatch=mismatch,row=row,col=col,extent=frame['extents'][row-1],requested_end=end)
                except (AssertionError,ValueError,oracle.OracleError,OSError) as error:
                    mismatch=False;record.update(mismatch=False,error=str(error))
                observations.append(record)
                (directory/'observations.json').write_text(json.dumps(observations,indent=2)+'\n')
                if calls%10==0 or mismatch:print('MINIMIZE seed=%d calls=%d pieces=%d bytes=%d mismatch=%s'%(seed,calls,len(items),len(data),mismatch),flush=True)
                return mismatch
            current=pieces(seed,stop);assert observe(current),'the named reference red did not reproduce'
            granularity=2
            while len(current)>=2 and calls<92 and time.monotonic()<deadline:
                size=math.ceil(len(current)/granularity);changed=False
                for start in range(0,len(current),size):
                    if calls>=92:break
                    candidate=current[:start]+current[start+size:]
                    if observe(candidate):current=candidate;granularity=max(2,granularity-1);changed=True;break
                if not changed:
                    if granularity>=len(current):break
                    granularity=min(len(current),granularity*2)
            for repeat in range(3):assert observe(current),'minimized reference red was not stable'
            data=b''.join(current)+C+str(amount).encode()+b'X';(directory/'reduced.in').write_bytes(data)
            manifest['streams']['fresh-%04d'%seed]={'calls':calls,'pieces':len(current),'bytes':len(data),'input_sha256':hashlib.sha256(data).hexdigest(),'repeats':3}
            (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
            print('REDUCED seed=%d calls=%d pieces=%d bytes=%d input=%r'%(seed,calls,len(current),len(data),data),flush=True)
    print('MEASUREMENTS finite-reference-minimization complete',flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
