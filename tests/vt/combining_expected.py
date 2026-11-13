"""Independent complete contract frames for the fixed combining-edge inputs."""
from expectations import blank


def expected(name):
    cols, rows = (6, 4) if name == 'unwritten-resized' else (12, 2)
    result = blank(cols, rows)
    result['title'] = b'probe'.hex()
    if name == 'column-zero':
        # No cell exists to the left of column1: the existing printing rule
        # drops the mark, including when the addressing parameter was zero.
        return result
    if name == 'wide-trailing-half':
        result['rows'][0][0] = [2, 'U+4E2D+U+0301', '-']
        result['rows'][0][1] = [0, '-', '-']
        result['extents'][0] = 2
        result['cursor']['col'] = 3
        return result
    if name == 'last-column-pending':
        result['rows'][0][11] = [1, 'U+005A+U+0301', '-']
        result['extents'][0] = 12
        result['cursor'].update(col=12, pending_wrap=1)
        return result
    col, cursor = {'unwritten-primary': (4, 5), 'unwritten-alternate': (4, 5),
                   'unwritten-resized': (4, 5), 'after-erase': (3, 4),
                   'last-column-addressed': (11, 12)}[name]
    result['rows'][0][col - 1] = [1, 'U+0020+U+0301', '-']
    result['extents'][0] = col
    result['cursor']['col'] = cursor
    if name == 'unwritten-alternate':
        # The three DECRQM selectors report the shared active screen, not
        # independent latch bits (also explicit in this case's raw A reply).
        for mode in ('alternate-screen-47', 'alternate-screen-1047', 'alternate-screen-1049'):
            result['modes'][mode] = 1
    return result
