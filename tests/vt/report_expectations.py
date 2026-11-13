"""Approved reference-only report fixtures; never candidate-derived values."""
import copy
import screen


def parts(attrs):
    return [] if attrs=='-' else attrs.split(',')


def foreground(values):
    selected=[value for value in values if value.startswith('fg=')]
    assert len(selected)<=1
    return selected[0] if selected else None


def replace_foreground(values,new):
    return [new if value.startswith('fg=') else value for value in values]


def recompose_no_bold(name,background_reference,no_bold_reference):
    if name=='fresh-0032':
        raise ValueError('opposite bright promotion remains outside the report fixtures')
    reduced=copy.deepcopy(background_reference)
    recomposed=copy.deepcopy(background_reference)
    changed=set()
    assert background_reference['size']==no_bold_reference['size']
    for r,row in enumerate(background_reference['rows']):
        for c,cell in enumerate(row):
            before=parts(cell[2]); after=parts(no_bold_reference['rows'][r][c][2])
            without=[value for value in before if value!='bold']
            old_fg,new_fg=foreground(before),foreground(after)
            if old_fg!=new_fg:
                assert 'bold' in before, ('foreground changed on a nonbold cell',r+1,c+1)
                assert old_fg and new_fg and old_fg.startswith('fg=idx:') and new_fg.startswith('fg=idx:')
                old_index,new_index=int(old_fg[7:]),int(new_fg[7:])
                assert 0<=old_index<16 and 0<=new_index<16 and old_index^new_index==8
                without=replace_foreground(without,new_fg)
                recomposed['rows'][r][c][2]=','.join(replace_foreground(before,new_fg))
                changed.add((r+1,c+1))
            reduced['rows'][r][c][2]=','.join(without) or '-'
    # Original bold removal plus the bounded xor8 foreground is the ONLY
    # allowed difference, including every metadata, glyph and width field.
    differences=screen.compare(reduced,no_bold_reference)
    assert not differences, ('no-bold reference changed another field',differences[:20])
    return recomposed,changed


def with_tab_one(reference,present):
    result=copy.deepcopy(reference)
    assert 1 not in result['tabs'], 'this fixture exists because DECTABSR omits1'
    if present:result['tabs']=sorted([1,*result['tabs']])
    return result
