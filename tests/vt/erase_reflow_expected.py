"""Independent D6/R1 frames: written erase suffixes are logical content."""
from expectations import blank


def expected(kind, painted, phase):
    narrowed = phase == 'narrowed'
    cols, rows = (6, 8) if narrowed else (12, 4)
    result = blank(cols, rows)
    result['title'] = b'probe'.hex()
    paint = 'bg=idx:5' if painted else '-'
    if kind == 'whole-row':
        # Full-row paint is not logical content. It clips to the current row;
        # resize-only widening restores the original retained paint workspace.
        for col in range(cols):
            result['rows'][0][col][2] = paint
        result['cursor']['col'] = 5
        return result
    if kind == 'after-last-glyph':
        cells = [[1, 'U+%04X' % cp, '-'] for cp in b'abcd'] + [[1, 'U+0020', paint] for _ in range(5)]
        cursor = (1, 5)
    elif kind == 'between-glyphs':
        cells = [[1, 'U+0061', '-']] + [[1, 'U+0020', paint] for _ in range(8)] + [[1, 'U+005A', '-']]
        cursor = (1, 2)
    elif kind == 'softwrapped-continuation':
        cells = [[1, 'U+%04X' % cp, '-'] for cp in b'abcdefghijkl'] + [[1, 'U+0020', paint] for _ in range(5)]
        cursor = (3, 1) if narrowed else (2, 1)
    else:
        raise ValueError('unknown independent erase/reflow case')
    for offset, cell in enumerate(cells):
        row, col = divmod(offset, cols)
        result['rows'][row][col] = cell
        result['extents'][row] = col + 1
    result['cursor'].update(row=cursor[0], col=cursor[1])
    return result
