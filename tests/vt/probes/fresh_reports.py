#!/usr/bin/env python3
"""37 complete dumps plus 31 status processes: at most 105 terminal processes.

21 no-bold inputs (promotion32 is diagnostic only), 16 erase interactions,
138 absolute DECCIR queries and 169 nonmoving checksum synchronization barriers.
No candidate program or candidate expected value is read.
"""
import argparse,hashlib,json,os,subprocess,sys,termios,tty
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/oracle'));import run as oracle;import screen
from feeder import Tty
sys.path.insert(0,str(ROOT/'tools/vt'));from repair_background_fixture import repair
from report_fixture import without_bold,tab_operations,column_one
sys.path.insert(0,str(ROOT/'tests/vt'));from origin_fixture import dump
from report_expectations import recompose_no_bold
sys.path.insert(0,str(ROOT/'tools/corpus'));import fuzz
E=b'\x1b';C=E+b'[';HEAD=E+b']2;probe\x07'+C+b'2 q'


def erase_cases():
    erased=C+b'5G'+C+b'7X';spaces=b'abcd'+b' '*7
    bodies={
      'erased-tail-wide':erased+'中'.encode(),'erased-tail-narrow':erased+b'X',
      'erased-tail-wide-lf':erased+'中'.encode()+b'\n','erased-tail-narrow-lf':erased+b'X\n',
      'erased-tail-primary-scroll':C+b'2;1Habcd'+C+b'7X\n',
      'erased-tail-alternate-scroll':C+b'?47h'+C+b'2;1Habcd'+C+b'7X\n',
      'erased-tail-lower-region-scroll':C+b'2;3r'+C+b'3;1Habcd'+C+b'7X\n',
      'erased-tail-delete':erased+C+b'P','erased-tail-insert':erased+C+b'@',
      'erased-tail-nonblank-wide':erased+C+b'11GZ'+C+b'5G'+'中'.encode(),
      'literal-tail-wide':spaces+C+b'5G'+'中'.encode(),'literal-tail-narrow':spaces+C+b'5GX',
      'literal-tail-primary-scroll':C+b'2;1H'+spaces+b'\n',
      'literal-tail-alternate-scroll':C+b'?47h'+C+b'2;1H'+spaces+b'\n',
      'erased-tail-cursor-only':erased+C+b'2;1H',
      'left-erased-tail-wide':C+b'11G'+C+b'1K'+C+b'5G'+'中'.encode(),
    }
    assert len(bodies)==16
    return {name:(HEAD+body,12,4 if 'lower-region' in name else 2) for name,body in bodies.items()}


def tab_inner(source,out):
    data=source.read_bytes();operations=tab_operations(data);old=termios.tcgetattr(0)
    try:
        tty.setraw(0);terminal=Tty(20);at=0;positions=[]
        for operation in operations:
            terminal.write(data[at:operation['offset']]);terminal.sync()
            reply=terminal.ask(b'\x1b[1$w',b'\x1b\\')
            fields=oracle.reply_field(reply.decode('ascii'),'\x1bP1$u','\x1b\\').split(';')
            row,col=int(fields[0]),int(fields[1]);assert 1<=row<=24 and 1<=col<=80
            positions.append({**operation,'row':row,'col':col,'deccir_hex':reply.hex()})
            terminal.write(data[operation['offset']:operation['end']]);at=operation['end']
        terminal.write(data[at:]);terminal.sync()
        record={'input_sha256':hashlib.sha256(data).hexdigest(),'positions':positions,
          'DECCIR_queries':len(operations),'checksum_barriers':len(operations)+1,
          'tab_one':column_one(operations,[position['col'] for position in positions])}
        out.write_text(json.dumps(record,indent=2)+'\n');return 0
    except Exception as error:
        out.write_text(json.dumps({'error':str(error)})+'\n');return 1
    finally:termios.tcsetattr(0,termios.TCSANOW,old)


def status_pass(display,source,out):
    command=['xterm','-u8','-geometry','80x24','-fn','fixed']
    for key,value in oracle.RESOURCES.items():command+=['-xrm','XTerm*%s: %s'%(key,value)]
    command+=['-e',sys.executable,'-I',str(Path(__file__).resolve()),'--tab-inner','--source',str(source.resolve()),'--out',str(out.resolve())]
    env={'DISPLAY':display.name,'LC_ALL':'C.UTF-8','PATH':os.environ['PATH'],'HOME':str(out.parent.resolve()),'TERM':'xterm-256color'}
    done=subprocess.run(command,env=env,capture_output=True,timeout=120)
    assert done.returncode==0 and out.exists(),(done.returncode,done.stderr[-500:])
    result=json.loads(out.read_text());assert 'error' not in result,result
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--baseline',type=Path);p.add_argument('--tab-inner',action='store_true',help=argparse.SUPPRESS);p.add_argument('--source',type=Path)
    a=p.parse_args()
    if a.tab_inner:return tab_inner(a.source,a.out)
    if not a.baseline:p.error('--baseline required')
    plan_path=ROOT/'tests/vt/fresh-report-cases.json';plan=json.loads(plan_path.read_text())
    assert len(plan['no_bold'])==21 and len(plan['tab_status'])==31
    a.out.mkdir(parents=True,exist_ok=False)
    m={'schema':1,'complete_dump_count':37,'status_processes':31,'terminal_processes':105,
      'plan_sha256':hashlib.sha256(plan_path.read_bytes()).hexdigest(),
      'pins_sha256':hashlib.sha256((ROOT/'warren-oracle.toml').read_bytes()).hexdigest(),'cases':{},'tab_status':{},'errors':[]}
    print('BUNDLE complete-dumps=37 status-processes=31 terminal-processes=105 DECCIR-queries=138 checksum-barriers=169 hard-cap-dumps=40',flush=True)
    def save():(a.out/'manifest.json').write_text(json.dumps(m,indent=2)+'\n')
    with oracle.Display() as display:
        for name,binding in plan['no_bold'].items():
            data=fuzz.stream(int(name[-4:]),4096);assert hashlib.sha256(data).hexdigest()==binding['original_sha256']
            fixed,events=repair(data);assert hashlib.sha256(fixed).hexdigest()==binding['background_input_sha256']
            raw=(a.baseline/name/'background-repaired-reference.screen').read_bytes()
            assert hashlib.sha256(raw).hexdigest()==binding['background_screen_sha256']
            original=screen.loads(raw.decode());modified,edits=without_bold(fixed)
            source=a.out/(name+'.in');source.write_bytes(modified);work=a.out/name
            entry={'kind':'promotion-diagnostic-only' if binding['diagnostic_only'] else 'no-bold-report-fixture',
              'input_sha256':hashlib.sha256(modified).hexdigest(),'size':[80,24],'edits':edits}
            try:
                got=dump(display,source.resolve(),80,24,work.resolve())
                encoded=screen.dumps(got).encode();(work/'got.screen').write_bytes(encoded);entry['screen_sha256']=hashlib.sha256(encoded).hexdigest()
                if binding['diagnostic_only']:
                    entry['reference_only_differences']=screen.compare(original,got)
                else:
                    recomposed,cells=recompose_no_bold(name,original,got)
                    model=screen.dumps(recomposed).encode();(work/'recomposed.screen').write_bytes(model)
                    entry['recomposed_sha256']=hashlib.sha256(model).hexdigest();entry['foreground_cells']=[list(cell) for cell in sorted(cells)]
                print('MEASURE %s kind=%s corrected-FG-cells=%d'%(name,entry['kind'],len(entry.get('foreground_cells',[]))),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError,subprocess.TimeoutExpired) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;save()
        for name,(data,cols,rows) in erase_cases().items():
            source=a.out/(name+'.in');source.write_bytes(data);work=a.out/name
            entry={'kind':'erase-interaction','input_sha256':hashlib.sha256(data).hexdigest(),'size':[cols,rows]}
            try:
                got=dump(display,source.resolve(),cols,rows,work.resolve())
                encoded=screen.dumps(got).encode();(work/'got.screen').write_bytes(encoded)
                entry['screen_sha256']=hashlib.sha256(encoded).hexdigest()
                print('MEASURE %s extents=%s'%(name,got['extents']),flush=True)
            except (AssertionError,oracle.OracleError,ValueError,OSError,subprocess.TimeoutExpired) as error:
                entry['error']=str(error);m['errors'].append(name);print('MEASURE-ERROR',name,str(error),flush=True)
            m['cases'][name]=entry;save()
        queries=barriers=0
        for name,digest in plan['tab_status'].items():
            data=fuzz.stream(int(name[-4:]),4096);assert hashlib.sha256(data).hexdigest()==digest
            source=a.out/(name+'.tabs.in');source.write_bytes(data);out=a.out/(name+'.tabs.json')
            try:
                record=status_pass(display,source,out);assert record['input_sha256']==digest
                queries+=record['DECCIR_queries'];barriers+=record['checksum_barriers'];m['tab_status'][name]=record
                print('MEASURE tabs-%s tab1=%s queries=%d'%(name,record['tab_one'],record['DECCIR_queries']),flush=True)
            except (AssertionError,ValueError,OSError,subprocess.TimeoutExpired) as error:
                m['errors'].append('tabs-'+name);print('MEASURE-ERROR tabs-'+name,str(error),flush=True)
            save()
    assert queries==138 and barriers==169,(queries,barriers)
    print('MEASUREMENTS dumps=37 status-processes=31 errors=%d'%len(m['errors']),flush=True)
    return bool(m['errors'])


if __name__=='__main__':raise SystemExit(main())
