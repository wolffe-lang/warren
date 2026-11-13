"""D12-only reference fixture construction; the ordinary validator is unchanged.

All cells still pass the original print/checksum/rendition finish validator.
The only exceptional report is independently guarded unsigned relative CPR;
absolute position comes from DECCIR, never candidate output or invented bytes.
"""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/oracle'))
import run as oracle
import screen


def contract_screen(a):
    cols,rows=a['size']
    cpr=[int(value) for value in oracle.reply_field(a['cpr'],'\x1b[','R').split(';')]
    cir=oracle.reply_field(a['deccir'],'\x1bP1$u','\x1b\\').split(';')
    row,col=int(cir[0]),int(cir[1])
    top,bottom=[int(value) for value in oracle.reply_field(a['decstbm'],'\x1bP1$r','r\x1b\\').split(';')]
    modes={}
    for family,head in (('dec','\x1b[?'),('ansi','\x1b[')):
        for number,answer in a[family+'_modes'].items():
            reported,value=oracle.reply_field(answer,head,'$y').split(';')
            assert reported==number
            modes[screen.MODE_NAMES[family][int(number)]]={'1':1,'3':1,'2':0,'4':0}.get(value,'?')
    assert modes['origin']==1 and 1<=row<top<=bottom<=rows and 1<=col<=cols
    relative=row-top+1
    assert len(cpr)==2 and cpr==[relative%65536,col], 'D12 requires the exact source-reported unsigned relative row and unchanged column'
    title=bytes.fromhex(a['title'])
    assert title.startswith(b'\x1b]l') and title.endswith(b'\x1b\\')
    tabs=oracle.reply_field(a['dectabsr'],'\x1bP2$u','\x1b\\')
    shape=int(oracle.reply_field(a['decscusr'],'\x1bP1$r',' q\x1b\\'))
    result={'size':[cols,rows],'cursor':{'row':row,'col':col,'shape':shape,
        'visible':modes['cursor-visible'],'pending_wrap':int(bool(ord(cir[5])&8))},
        'region':[top,bottom],'tabs':[int(value) for value in tabs.split('/') if value],
        'title':title[3:-2].hex(),'modes':modes,'rows':[],'extents':[]}
    printed=oracle.parse_print(a['print'],rows)
    for number in range(rows):
        cells=oracle.lay_out(printed[number],a['checksums'][number],cols)
        result['rows'].append(cells); result['extents'].append(len(cells))
    note={'divergence':'D12','absolute_row':row,'region_top':top,'signed_relative_row':relative,
          'reference_cpr_row':cpr[0],'warren_cpr_row':1,'column':col}
    return result,note


def finish_d12(display,source,cols,rows,work,a):
    frame,note=contract_screen(a)
    work.mkdir(parents=True,exist_ok=True)
    layout=work/'continuation.json'
    layout.write_text(json.dumps([[col+1 for col,cell in enumerate(row) if cell[0]==0] for row in frame['rows']]))
    s=oracle.run_pass(display,'S',source,cols,rows,work,extra=[layout])
    result=oracle.finish(frame,a,s)
    (work/'D12.json').write_text(json.dumps(note,indent=2)+'\n')
    return result


def dump(display,source,cols,rows,work):
    """Same two passes; only D12's guarded metadata uses the contract builder."""
    work.mkdir(parents=True,exist_ok=True)
    a=oracle.run_pass(display,'A',source,cols,rows,work)
    try:
        frame=oracle.describe(a)
    except oracle.OracleError:
        # A nontrigger, changed column or different inconsistency is still red.
        return finish_d12(display,source,cols,rows,work,a)
    try:
        special,note=contract_screen(a)
    except (AssertionError,ValueError,oracle.OracleError):
        special=None
    if special is not None:
        # Relative zero also violates the one-based CPR contract even though
        # the old arithmetic consistency check can accept it; name it too.
        return finish_d12(display,source,cols,rows,work,a)
    layout=work/'continuation.json'
    layout.write_text(json.dumps([[col+1 for col,cell in enumerate(row) if cell[0]==0] for row in frame['rows']]))
    s=oracle.run_pass(display,'S',source,cols,rows,work,extra=[layout])
    return oracle.finish(frame,a,s)
