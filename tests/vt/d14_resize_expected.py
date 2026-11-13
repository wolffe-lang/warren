"""Independent D6 frames for the three fixed D14 resize observations."""
from expectations import blank


def resized(name, reference=False):
    if name not in ('scroll-default-resized', 'scroll-background-resized', 'fresh-background-resized'):
        raise ValueError('not a declared D6/D14 resized fixture')
    scrolling = name.startswith('scroll-')
    painted = name != 'scroll-default-resized'
    result = blank(6, 8)
    result['title'] = b'probe'.hex()
    # One blank older line is pulled from bounded history in the scroll cases.
    row = 4 if scrolling else 3  # zero-based
    result['cursor'].update(row=row + 1, col=5)
    if reference:
        for col, cp in enumerate(b'abcd'):
            result['rows'][row][col] = [1, 'U+%04X' % cp, 'bg=idx:5' if painted else '-']
        if painted:
            for col in range(6):
                result['rows'][row][col][2] = 'bg=idx:5'
        result['extents'][row] = 4 if scrolling else 6
        return result
    for offset in range(12 if scrolling and painted else 9):
        r, c = divmod(offset, 6)
        attrs = 'bg=idx:5' if painted else '-'
        chars = 'U+%04X' % b'abcd'[offset] if offset < 4 else 'U+0020'
        result['rows'][row + r][c] = [1, chars, attrs]
    result['extents'][row] = 6
    result['extents'][row + 1] = 3
    return result
