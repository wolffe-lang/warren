#!/usr/bin/env python3
"""25 complete frames, 45 new terminal passes: D12 completion/motions and ECH.

Five preserved A passes need only S; eight motion and twelve erase cases need
both passes. No candidate program or candidate-produced expected frame is used.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle')); import run as oracle; import screen
sys.path.insert(0,str(ROOT/'tests/vt')); from origin_fixture import dump,finish_d12
E=b'\x1b'; C=E+b'['; HEAD=E+b']2;probe\x07'+C+b'2 q'


def fresh_cases():
    base=C+b'?6h'+C+b'2;3H'+E+b'7'+C+b'5;8r'+E+b'8'
    bodies={
      'motion-cud-one':base+C+b'B','motion-cud-two':base+C+b'2B','motion-cud-many':base+C+b'99B',
      'motion-cuu-one':base+C+b'A','motion-cuu-many':base+C+b'99A','motion-lf':base+b'\n',
      'motion-wrap-above':C+b'?6h'+C+b'2;12HZ'+E+b'7'+C+b'5;8r'+E+b'8Q',
      'motion-wrap-into-region':C+b'?6h'+C+b'4;12HZ'+E+b'7'+C+b'5;8r'+E+b'8Q',
    }
    result={name:(HEAD+body,12,8,'origin-motion') for name,body in bodies.items()}
    edits={
      'ech-blank-default-one':C+b'5G'+C+b'X',
      'ech-blank-explicit-one':C+b'5G'+C+b'1X',
      'ech-blank-two':C+b'5G'+C+b'2X',
      'ech-blank-three':C+b'5G'+C+b'3X',
      'ech-blank-seven':C+b'5G'+C+b'7X',
      'ech-blank-to-end':C+b'5G'+C+b'8X',
      'ech-past-gap-two':b'ab'+C+b'5G'+C+b'2X',
      'ech-after-content-two':b'ab'+C+b'3G'+C+b'2X',
      'ech-after-content-one':b'ab'+C+b'3G'+C+b'X',
      'ech-insert-mode-two':C+b'4h'+C+b'5G'+C+b'2X',
      'ech-background-two':C+b'42m'+C+b'5G'+C+b'2X',
      'el-left-blank-control':C+b'5G'+C+b'1K',
    }
    result.update({name:(HEAD+body,12,4,'erase-extent') for name,body in edits.items()})
    assert len(result)==20
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    original=ROOT/'tests/vt/reference/origin/original'
    old=json.loads((original/'manifest.json').read_text())
    assert len(old['errors'])==5
    manifest={'schema':1,'complete_frames':25,'new_terminal_passes':45,
      'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),
      'original_manifest_sha256':hashlib.sha256((original/'manifest.json').read_bytes()).hexdigest(),'cases':{},'errors':[]}
    print('BUNDLE complete-frames=25 new-terminal-passes=45 hard-cap-frames=25',flush=True)
    with oracle.Display() as display:
        for name in old['errors']:
            source=original/(name+'.in'); entry=old['cases'][name]
            assert hashlib.sha256(source.read_bytes()).hexdigest()==entry['input_sha256']
            raw_a=json.loads((original/name/'A.json').read_text());raw_a['print']=(original/name/'A.print').read_bytes()
            label='complete-'+name;work=a.out/label
            record={'kind':'D12-completed-S-only','original_case':name,'input_sha256':entry['input_sha256'],'size':entry['size']}
            try:
                got=finish_d12(display,source.resolve(),*entry['size'],work.resolve(),raw_a)
                raw=screen.dumps(got).encode();(work/'got.screen').write_bytes(raw)
                record['screen_sha256']=hashlib.sha256(raw).hexdigest()
                print('MEASURE %s cursor=%s'%(label,got['cursor']),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                record['error']=str(error);manifest['errors'].append(label);print('MEASURE-ERROR',label,str(error),flush=True)
            manifest['cases'][label]=record
            (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
        for name,(data,cols,rows,kind) in fresh_cases().items():
            source=a.out/(name+'.in');source.write_bytes(data);work=a.out/name
            record={'kind':kind,'input_sha256':hashlib.sha256(data).hexdigest(),'size':[cols,rows]}
            try:
                got=dump(display,source.resolve(),cols,rows,work.resolve())
                raw=screen.dumps(got).encode();(work/'got.screen').write_bytes(raw)
                record['screen_sha256']=hashlib.sha256(raw).hexdigest()
                record['report_class']='D12' if (work/'D12.json').exists() else 'strict'
                print('MEASURE %s cursor=%s extents=%s class=%s'%(name,got['cursor'],got['extents'],record['report_class']),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                record['error']=str(error);manifest['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            manifest['cases'][name]=record
            (a.out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('MEASUREMENTS frames=25 errors=%d'%len(manifest['errors']),flush=True)
    return bool(manifest['errors'])


if __name__=='__main__':raise SystemExit(main())
