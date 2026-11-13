#!/usr/bin/env python3
"""No-bold fixtures permit only the approved per-cell flag/foreground bound."""
from pathlib import Path
import copy,sys
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tools/oracle'));sys.path.insert(0,str(ROOT/'tests/vt'))
from expectations import blank,text_row
from report_expectations import recompose_no_bold


def main():
    old=blank(12,4);text_row(old,0,[88],'bold,fg=idx:1')
    no_bold=copy.deepcopy(old);no_bold['rows'][0][0][2]='fg=idx:9'
    before=copy.deepcopy(old)
    fixed,cells=recompose_no_bold('fresh-0015',old,no_bold)
    assert cells=={(1,1)} and fixed['rows'][0][0][2]=='bold,fg=idx:9' and old==before
    plants=[]
    glyph=copy.deepcopy(no_bold);glyph['rows'][0][0][1]='U+0059';plants.append(glyph)
    cursor=copy.deepcopy(no_bold);cursor['cursor']['col']=7;plants.append(cursor)
    background=copy.deepcopy(no_bold);background['rows'][0][0][2]='fg=idx:9,bg=idx:2';plants.append(background)
    not_xor=copy.deepcopy(no_bold);not_xor['rows'][0][0][2]='fg=idx:10';plants.append(not_xor)
    extra_flag=copy.deepcopy(no_bold);extra_flag['rows'][0][0][2]='italic,fg=idx:9';plants.append(extra_flag)
    for changed in plants:
        try:recompose_no_bold('fresh-0015',old,changed)
        except (AssertionError,ValueError):pass
        else:raise AssertionError('change outside no-bold field bound accepted')
    invisible=blank(12,4);text_row(invisible,0,[32],'bold,fg=idx:1')
    invisible_no_bold=copy.deepcopy(invisible);invisible_no_bold['rows'][0][0][2]='fg=idx:10'
    _,n1_cells=recompose_no_bold('n1-control',invisible,invisible_no_bold)
    assert not n1_cells, 'existing N1 makes nondrawing blank foreground unobservable'
    try:recompose_no_bold('fresh-0032',old,no_bold)
    except ValueError:pass
    else:raise AssertionError('unruled opposite-promotion case accepted')
    print('PASS no-bold complete-frame bounds glyph cursor background other-flags wrong-xor promotion32-refused no-mutation')


if __name__=='__main__':main()
