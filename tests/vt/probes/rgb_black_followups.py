#!/usr/bin/env python3
"""28 dumps and15 SGR observations: at most71 terminal processes.

Measure RGB blank extents, D13 bold-clear/order controls and its full-stream
source-repaired frame. No native output supplies expected data.
"""
import argparse,copy,hashlib,json,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle;import screen
sys.path.insert(0,str(ROOT/'tests/vt'));from origin_fixture import dump
sys.path.insert(0,str(ROOT/'tools/vt'));from legacy_black_fixture import repair as black_repair
from repair_background_fixture import repair as background_repair
E=b'\x1b';C=E+b'[';HEAD=E+b']2;probe\x07'+C+b'2 q'


def cases():
    ech=C+b'5G'+C+b'7X';rgb=C+b'48;2;1;2;3m'
    bodies={
      'erase-default':ech,'erase-index0':C+b'40m'+ech,'erase-index2':C+b'42m'+ech,
      'erase-rgb-black':C+b'48;2;0;0;0m'+ech,
      'erase-rgb-green':C+b'48;2;0;128;0m'+ech,'erase-rgb-sample':rgb+ech,
      'erase-rgb-content':rgb+b'abcd'+C+b'7X',
      'erase-rgb-literal-tail':rgb+b'abcd'+b' '*7+C+b'5G'+C+b'7X',
      'erase-rgb-el-left':rgb+C+b'5G'+C+b'1K',
      'erase-rgb-insert':rgb+C+b'5G'+C+b'3@',
      'erase-rgb-one':rgb+C+b'5G'+C+b'X',
      'erase-default-then-rgb':ech+rgb+C+b'7X',
    }
    result={name:(HEAD+body,12,4,False) for name,body in bodies.items()}
    controls={
      'legacy-clear-bold-next-glyph':C+b'1;30mm'+C+b'22mn',
      'legacy-clear-bold-pen-only':C+b'1;30mm'+C+b'22m',
      'legacy-clear-then30-next-glyph':C+b'1;30mm'+C+b'22m'+C+b'30mn',
      'legacy-clear-then30-pen-only':C+b'1;30mm'+C+b'22m'+C+b'30m',
      'indexed-before-bold':C+b'38;5;0m'+C+b'1mm',
      'indexed-after-bold':C+b'1m'+C+b'38;5;0mm',
      'indexed-before-bold-cleared':C+b'38;5;0m'+C+b'1mm'+C+b'22mn',
      'bright-black-cleared':C+b'1;90mm'+C+b'22mn',
    }
    for code in range(31,38):controls['strict-bold-legacy-%d'%code]=C+('1;%dmm'%code).encode()
    result.update({name:(HEAD+body,12,4,True) for name,body in controls.items()})
    assert len(result)==27 and sum(row[3] for row in result.values())==15
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);p.add_argument('--baseline',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    pen_pass=runpy.run_path(str(ROOT/'tests/vt/probes/default_restoration.py'))['pen_pass']
    selected=cases();source=runpy.run_path(str(ROOT/'tools/corpus/fuzz.py'))['stream'](32,4096)
    bg,background_events=background_repair(source)
    assert bg==(a.baseline/'fresh-0032/background-repaired.in').read_bytes()
    repaired,edits=black_repair(bg)
    selected['fresh-0032-D13']=(repaired,80,24,False)
    m={'schema':1,'dump_budget':28,'pen_budget':15,'terminal_process_budget':71,
      'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),'cases':{},'errors':[]}
    print('BUNDLE dumps-at-most=28 pen-statuses-at-most=15 terminal-processes-at-most=71',flush=True)
    with oracle.Display() as display:
        for name,(data,cols,rows,pen) in selected.items():
            path=a.out/(name+'.in');path.write_bytes(data);work=a.out/name
            entry={'input_sha256':hashlib.sha256(data).hexdigest(),'size':[cols,rows],'pen_status':pen}
            if name=='fresh-0032-D13':entry['edits']=edits
            try:
                got=dump(display,path.resolve(),cols,rows,work.resolve())
                raw=screen.dumps(got).encode();(work/'got.screen').write_bytes(raw);entry['screen_sha256']=hashlib.sha256(raw).hexdigest()
                if pen:entry['sgr_report_hex']=pen_pass(display,path,cols,rows,work/'pen.json')
                if name=='fresh-0032-D13':
                    original=screen.loads((a.baseline/'fresh-0032/background-repaired-reference.screen').read_text())
                    changed={(r+1,c+1) for r,row in enumerate(original['rows']) for c,cell in enumerate(row) if
                      next((v for v in cell[2].split(',') if v.startswith('fg=')),None)!=next((v for v in got['rows'][r][c][2].split(',') if v.startswith('fg=')),None)}
                    assert changed=={(16,19)},changed
                    model=copy.deepcopy(original);parts=model['rows'][15][18][2].split(',')
                    assert 'bold' in parts and 'fg=idx:8' in parts
                    model['rows'][15][18][2]=','.join('fg=idx:0' if v=='fg=idx:8' else v for v in parts)
                    assert not screen.compare(model,got),screen.compare(model,got)[:20]
                    entry['foreground_cells']=[[16,19]];entry['original_reference_sha256']=hashlib.sha256((a.baseline/'fresh-0032/background-repaired-reference.screen').read_bytes()).hexdigest()
                print('MEASURE %s extents=%s first=%s pen=%s'%(name,got['extents'],got['rows'][0][:2],entry.get('sgr_report_hex','-')),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('MEASUREMENTS cases=28 errors=%d'%len(m['errors']),flush=True)
    return bool(m['errors'])


if __name__=='__main__':raise SystemExit(main())
