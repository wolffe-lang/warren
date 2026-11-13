#!/usr/bin/env python3
"""Eight binary dumps (16 terminal passes) for fresh saved-row structural reds."""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'))
import run as oracle
import screen
E=b'\x1b'; C=E+b'['; HEAD=E+b']2;probe\x07'+C+b'2 q'


def cases():
    bodies={
      'dec-above-new-region': C+b'?6h'+C+b'2;3H'+E+b'7'+C+b'5;8r'+E+b'8X',
      'dec-below-new-region': C+b'?6h'+C+b'7;3H'+E+b'7'+C+b'1;3r'+E+b'8X',
      '1048-above-new-region': C+b'?6h'+C+b'2;3H'+C+b'?1048h'+C+b'5;8r'+C+b'?1048lX',
      '1049-above-new-region': C+b'?6h'+C+b'2;3H'+C+b'?1049h'+C+b'5;8r'+C+b'?1049lX',
      'dec-inside-new-region-control': C+b'?6h'+C+b'6;3H'+E+b'7'+C+b'5;8r'+E+b'8X',
      'dec-origin-off-control': C+b'2;3H'+E+b'7'+C+b'5;8r'+E+b'8X',
    }
    result={name:(HEAD+body,12,8,{'kind':'saved-row-discriminator'}) for name,body in bodies.items()}
    stream=runpy.run_path(str(ROOT/'tools/corpus/fuzz.py'))['stream']
    for seed,needle in ((190,b']&QH\\'),(191,b'OXlAKb_w')):
        data=stream(seed,4096)
        at=data.index(needle)
        result['fresh-%04d-before-fragment'%seed]=(HEAD+data[:at],80,24,
          {'kind':'fresh-prefix-cursor-diagnostic','prefix_bytes':at,'original_sha256':hashlib.sha256(data).hexdigest()})
    assert len(result)==8
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); args.out.mkdir(parents=True,exist_ok=False)
    print('BUNDLE complete-dumps=8 terminal-passes=16 hard-cap=8',flush=True)
    manifest={'schema':1,'complete_dump_count':8,'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),'cases':{},'errors':[]}
    with oracle.Display() as display:
        for name,(data,cols,rows,provenance) in cases().items():
            source=args.out/(name+'.in'); source.write_bytes(data)
            entry={'input_sha256':hashlib.sha256(data).hexdigest(),'size':[cols,rows],**provenance}
            try:
                work=args.out/name
                got=oracle.dump(display,source.resolve(),cols,rows,work.resolve())
                raw=screen.dumps(got).encode(); (work/'got.screen').write_bytes(raw)
                entry['screen_sha256']=hashlib.sha256(raw).hexdigest()
                print('MEASURE %s cursor=%s region=%s origin=%s'%(name,got['cursor'],got['region'],got['modes']['origin']),flush=True)
            except (oracle.OracleError,ValueError,OSError) as error:
                entry['error']=str(error); manifest['errors'].append(name)
                print('MEASURE-ERROR %s %s'%(name,error),flush=True)
            manifest['cases'][name]=entry
            (args.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('MEASUREMENTS cases=8 errors=%d'%len(manifest['errors']),flush=True)
    return bool(manifest['errors'])


if __name__=='__main__': raise SystemExit(main())
