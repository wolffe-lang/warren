"""Written full-screen expectations for the contract's named divergences."""
import copy
import re
import screen


def blank(cols=80, rows=24):
    modes = {name: 0 for family in screen.MODE_NAMES.values() for name in family.values()}
    for name in ('autowrap', 'cursor-visible', 'send-receive'):
        modes[name] = 1
    return {'size': [cols, rows], 'cursor': {'row': 1, 'col': 1, 'shape': 2,
            'visible': 1, 'pending_wrap': 0}, 'region': [1, rows],
            'tabs': list(range(9, cols + 1, 8)), 'title': '74', 'modes': modes,
            'rows': [[[1, 'U+0020', '-'] for _ in range(cols)] for _ in range(rows)],
            'extents': [0] * rows}


def text_row(result, row, values, attrs='-'):
    for col, cp in enumerate(values):
        result['rows'][row][col] = [1, 'U+%04X' % cp, attrs]
    result['extents'][row] = len(values)


def expected(suite, name, data, oracle):
    ruled = copy.deepcopy(oracle)
    assert ruled['modes']['synchronized-output'] == '?'
    mode = re.findall(rb'\x1b\[\?2026([hl])', data)
    ruled['modes']['synchronized-output'] = int(bool(mode) and mode[-1] == b'h')
    labels = ['D7']
    if suite != 'census':
        return labels, ruled
    if name == 'sgr-underline-colon':
        ruled = blank()
        text_row(ruled, 0, [88], 'underline')
        ruled['cursor']['col'] = 2
        labels.append('D1')
    elif name in ('sgr-underline-colour', 'sgr-underline-colour-colon', 'csi-many-params'):
        ruled = blank()
        text_row(ruled, 0, [88])
        ruled['cursor']['col'] = 2
        labels.append('D4' if name == 'csi-many-params' else 'D2')
    elif name in ('utf8-overlong', 'utf8-beyond'):
        ruled = blank()
        values = [97] + [0xFFFD] * (2 if name == 'utf8-overlong' else 4) + [98]
        text_row(ruled, 0, values)
        ruled['cursor']['col'] = len(values) + 1
        labels.append('D3')
    elif name in ('resize-narrower', 'resize-wider'):
        cols = 60 if name == 'resize-narrower' else 100
        ruled = blank(cols)
        text_row(ruled, 0, [121] * cols)
        if cols == 60:
            text_row(ruled, 1, [121] * 40)
            text_row(ruled, 2, [97, 98])
            ruled['cursor'].update(row=3, col=3)
        else:
            text_row(ruled, 1, [97, 98])
            ruled['cursor'].update(row=2, col=3)
        labels.append('D6')
    return labels, ruled
