#!/usr/bin/env python3
"""26 dumps/52 terminal passes: erase no-op state and pair-repair edge scope."""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle;import screen
sys.path.insert(0,str(ROOT/'tests/vt'));from origin_fixture import dump
E=b'\x1b';C=E+b'[';HEAD=E+b']2;probe\x07'+C+b'2 q';W='中'.encode()


def cases():
    eh=C+b'5G'+C+b'7X';clear=C+b'2K'
    erase={
      'fresh-erase-control':eh,'line-cleared-then-erase':clear+eh,
      'display-cleared-then-erase':C+b'2J'+eh,'end-cleared-then-erase':C+b'K'+eh,
      'left-full-clear-then-erase':C+b'12G'+C+b'1K'+eh,
      'cleared-content-then-erase':clear+b'abcd'+C+b'7X',
      'rgb-cleared-then-erase':C+b'48;2;1;2;3m'+clear+eh,
      'indexed-cleared-then-erase':C+b'42m'+clear+eh,
      'foreground-cleared-then-erase':C+b'38;5;211m'+clear+eh,
      'cleared-foreground-change':C+b'31m'+clear+C+b'32m'+eh,
      'cleared-background-change':clear+C+b'42m'+eh,
      'cleared-single-glyph-then-erase':clear+C+b'5GX'+eh,
    }
    result={name:(HEAD+body,12,4) for name,body in erase.items()}
    for wrap,where,start in ((False,'interior',5),(True,'edge',11),(True,'interior',5)):
        old=(C+b'?7h' if wrap else C+b'?7l')+C+b'2;8;9;45m'+C+str(start).encode()+b'G'+W
        for side,col in (('lead',start),('tail',start+1)):
            name='%s-%s-wrap%d'%(where,side,int(wrap))
            result[name]=(HEAD+old+C+str(col).encode()+b'GX',12,4)
        result['%s-new-pen-tail-wrap%d'%(where,int(wrap))]=(HEAD+old+C+b'0;42m'+C+str(start+1).encode()+b'GX',12,4)
    for kind in ('delete','insert','erase'):
        old=C+b'?7l'+C+b'2;8;9;45m'+C+b'5G'+W+C+b'0;42m'+C+(b'5G' if kind=='erase' else b'6G')
        result['interior-'+kind]=(HEAD+old+C+{'delete':b'P','insert':b'@','erase':b'X'}[kind],12,4)
    f175=C+b'2;3r'+C+b'?6h'+C+b'?7l'+C+b'2;1H'+C+b'1;4;5;8;38;5;211;48;2;5;209;79m'+C+b'2K'+b'A'*35+C+b'12X'
    f54=C+b'?47h'+C+b'6;17r'+C+b'17;1H'+C+b'4h'+C+b'3;7;8;9;48;2;244;208;208m'+C+b'2K'+b'A'*9+C+b'30X'
    result['fresh175-equivalent-visible-state']=(HEAD+f175,80,24)
    result['fresh54-equivalent-visible-state']=(HEAD+f54,80,24)
    assert len(result)==26
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    m={'schema':1,'dump_budget':26,'terminal_process_budget':52,'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),'cases':{},'errors':[]}
    print('BUNDLE dumps-at-most=26 terminal-processes-at-most=52',flush=True)
    with oracle.Display() as display:
        for name,(data,cols,rows) in cases().items():
            source=a.out/(name+'.in');source.write_bytes(data);work=a.out/name
            entry={'input_sha256':hashlib.sha256(data).hexdigest(),'size':[cols,rows]}
            try:
                got=dump(display,source.resolve(),cols,rows,work.resolve());raw=screen.dumps(got).encode();(work/'got.screen').write_bytes(raw)
                entry['screen_sha256']=hashlib.sha256(raw).hexdigest()
                cells=got['rows'][0]
                print('MEASURE %s extents=%s cells5-6=%s cells11-12=%s'%(name,got['extents'],cells[4:6],cells[10:12]),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('MEASUREMENTS cases=26 errors=%d'%len(m['errors']),flush=True);return bool(m['errors'])


if __name__=='__main__':raise SystemExit(main())
