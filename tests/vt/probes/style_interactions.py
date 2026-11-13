#!/usr/bin/env python3
"""At most40 dumps and6 SGR observations: 86 terminal processes, no source reads.

Isolate the four remaining fresh cases: erase under concealment, styled wide
repairs, and the separately unruled opposite-promotion/combining interaction.
"""
import argparse,hashlib,json,runpy,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle;import screen
sys.path.insert(0,str(ROOT/'tests/vt'));from origin_fixture import dump
E=b'\x1b';C=E+b'[';HEAD=E+b']2;probe\x07'+C+b'2 q';V='⃗'.encode();A='́'.encode();W='中'.encode()


def cases():
    invisible={
      'conceal-ech-seven':C+b'8m'+C+b'5G'+C+b'7X',
      'inverse-ech-seven':C+b'7m'+C+b'5G'+C+b'7X',
      'conceal-ech-one':C+b'8m'+C+b'5G'+C+b'X',
      'conceal-content-ech':C+b'8mabcd'+C+b'7X',
      'conceal-erase-visible-wide':C+b'8m'+C+b'5G'+C+b'7X'+C+b'28m'+W,
      'visible-erase-concealed-wide':C+b'5G'+C+b'7X'+C+b'8m'+W,
      'conceal-el-left':C+b'8m'+C+b'5G'+C+b'1K',
    }
    old=C+b'?7l'+C+b'2;8;9;45m'+C+b'11G'+W
    pairs={
      'styled-wide-lead':old+C+b'11GX','styled-wide-tail':old+C+b'12GX',
      'styled-wide-new-pen-tail':old+C+b'0;42m'+C+b'12GX',
      'styled-wide-erase-lead':old+C+b'0;42m'+C+b'11G'+C+b'X',
      'styled-wide-delete-tail':old+C+b'0;42m'+C+b'12G'+C+b'P',
      'styled-wide-insert-tail':old+C+b'0;42m'+C+b'12G'+C+b'@',
    }
    colours={
      'bold-zero-plain':C+b'1;30mm','bold-zero-vector':C+b'1;30mm'+V,
      'bold-zero-acute':C+b'1;30mm'+A,'bold-zero-underline-vector':C+b'1;4;30mm'+V,
      'bold-indexed-zero-vector':C+b'1;4;38;5;0mm'+V,'bold-one-vector':C+b'1;31mm'+V,
      'bold-eight-vector':C+b'1;90mm'+V,'bold-nine-vector':C+b'1;91mm'+V,
      'plain-zero-vector':C+b'30mm'+V,'bold-rgb-vector':C+b'1;38;2;1;2;3mm'+V,
      'bold-wide-zero-vector':C+b'1;30m'+W+V,'bold-blank-zero-vector':C+b'1;4;30m '+V,
    }
    late=C+b'4;30m'+C+b'1m'
    exact=C+b'4;48;5;10;30m'+C+b'48;2;227;86;220;1m'
    red=C+b'4;31m'+C+b'1m'
    order={'late-bold-zero-plain':late+b'm','late-bold-zero-vector':late+b'm'+V,
      'exact-bg-late-bold-plain':exact+b'm','exact-bg-late-bold-vector':exact+b'm'+V,
      'late-bold-one-plain':red+b'm','late-bold-one-vector':red+b'm'+V}
    result={name:(HEAD+body,12,4,False) for name,body in {**invisible,**pairs,**colours,**order}.items()}
    stream=runpy.run_path(str(ROOT/'tools/corpus/fuzz.py'))['stream']
    for seed,points in ((54,[(4084,'before-erase',True),(4089,'after-erase',True),(4090,'after-lf',False),(None,'end',False)]),
                        (175,[(3621,'before-erase',True),(3626,'after-erase',True),(3629,'after-wide',False)]),
                        (32,[(2820,'before-marked-glyph',True),(2824,'after-marked-glyph',True)])):
        data=stream(seed,4096)
        if seed==54:assert data[4084:4089]==C+b'30X'
        if seed==175:assert data[3621:3626]==C+b'12X' and data[3626:3629]=='あ'.encode()
        if seed==32:assert data[2820:2824]==b'm'+V
        for at,label,pen in points:
            result['fresh-%04d-%s'%(seed,label)]=(data[:at] if at is not None else data,80,24,pen)
    assert len(result)==40 and sum(pen for _,_,_,pen in result.values())==6
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False)
    pen_pass=runpy.run_path(str(ROOT/'tests/vt/probes/default_restoration.py'))['pen_pass']
    m={'schema':1,'dump_budget':40,'pen_budget':6,'terminal_process_budget':86,
       'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),'cases':{},'errors':[]}
    print('BUNDLE complete-dumps-at-most=40 SGR-statuses-at-most=6 terminal-processes-at-most=86 hard-cap-dumps=40',flush=True)
    with oracle.Display() as display:
        for name,(data,cols,rows,pen) in cases().items():
            source=a.out/(name+'.in');source.write_bytes(data);work=a.out/name
            entry={'input_sha256':hashlib.sha256(data).hexdigest(),'size':[cols,rows],'pen_status':pen}
            try:
                got=dump(display,source.resolve(),cols,rows,work.resolve())
                raw=screen.dumps(got).encode();(work/'got.screen').write_bytes(raw)
                entry['screen_sha256']=hashlib.sha256(raw).hexdigest()
                if pen:entry['sgr_report_hex']=pen_pass(display,source,cols,rows,work/'pen.json')
                nonblank=[(r+1,c+1,cell[1],cell[2]) for r,row in enumerate(got['rows']) for c,cell in enumerate(row) if cell[1]!='U+0020']
                print('MEASURE %s extents=%s samples=%s pen=%s'%(name,got['extents'],nonblank[:3],entry.get('sgr_report_hex','-')),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('MEASUREMENTS cases=40 errors=%d'%len(m['errors']),flush=True)
    return bool(m['errors'])


if __name__=='__main__':raise SystemExit(main())
