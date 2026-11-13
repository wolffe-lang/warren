#!/usr/bin/env python3
"""28 raw A/S captures (56 terminal processes) for new zero-width classes.

No assumption that a format scalar is retained is used to build a golden.
Raw print/checksum/layout evidence is retained even if the old cluster parser
cannot yet construct a complete frame.
"""
import argparse,hashlib,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle;import screen
E=b'\x1b';C=E+b'[';HEAD=E+b']2;probe\x07'+C+b'2 q'
POINTS=(0x1160,0x1161,0x11A8,0xD7B0,0xD7CB,0xFFF9,0x13430)


def cases():
    return {'zero-%04X-%s'%(cp,name):(HEAD+prefix+chr(cp).encode(),cp,name)
      for cp in POINTS for name,prefix in (('ascii',b'a'),('wide','中'.encode()),('unwritten',C+b'1;5H'),('first',b''))}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True);a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    selected=cases();assert len(selected)==28
    m={'schema':1,'terminal_process_budget':56,'cases':{},'errors':[]}
    print('BUNDLE raw-A+S=28 terminal-processes-at-most=56',flush=True)
    with oracle.Display() as display:
        for name,(data,cp,context) in selected.items():
            source=a.out/(name+'.in');source.write_bytes(data);work=a.out/name;work.mkdir()
            entry={'input_sha256':hashlib.sha256(data).hexdigest(),'scalar':'U+%04X'%cp,'context':context}
            try:
                raw=oracle.run_pass(display,'A',source.resolve(),12,4,work.resolve())
                layout=work/'continuation.json'
                # Only ASCII a, space, the stated nonzero-low16 scalar and
                # one CJK base occur: checksum0000 can only be its wide tail.
                tails=[[c+1 for c,value in enumerate(row) if value=='0000'] for row in raw['checksums']]
                assert tails==([[2],[],[],[]] if context=='wide' else [[],[],[],[]]),tails
                layout.write_text(json.dumps(tails))
                full=oracle.run_pass(display,'S',source.resolve(),12,4,work.resolve(),extra=[layout])
                try:
                    got=oracle.finish(oracle.describe(raw),raw,full)
                    (work/'got.screen').write_text(screen.dumps(got));entry['classification']='complete-reference-frame'
                except (oracle.OracleError,ValueError) as error:
                    entry.update(classification='raw-reference-report-or-layout-failure',validator_error=str(error))
                print('MEASURE %s CPR=%r print=%r class=%s'%(name,raw['cpr'],raw['print'],entry['classification']),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    print('MEASUREMENTS raw-cases=28 process-errors=%d'%len(m['errors']),flush=True);return bool(m['errors'])


if __name__=='__main__':raise SystemExit(main())
