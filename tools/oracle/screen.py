#!/usr/bin/env python3
"""The screen dump: its text form, the comparison, and the planted mutations.

docs/SCREEN-DUMP.md is the format's description. A screen is a dict:

  size      [cols, rows]
  cursor    {row, col, shape, visible, pending_wrap}   (1-based row and col)
  region    [top, bottom]
  tabs      [col, ...]
  title     hex of the title's bytes
  modes     {name: 0|1}
  extents   per row, the column of the last cell written since the row was
            last erased (0 for a row never written); what print screen prints
  rows      rows of cells; a cell is [width, chars, attrs]
            width 1 or 2, or 0 for the second half of a wide character
            chars 'U+0041' or 'U+0065+U+0301'; '-' in a continuation cell
            attrs '-' or a comma list in ATTR_ORDER, then fg=, then bg=
"""
import copy
import sys

ATTR_ORDER = ['bold', 'dim', 'italic', 'underline', 'double-underline', 'blink', 'inverse',
              'invisible', 'strike']
MODE_NAMES = {
    'dec': {1: 'application-cursor-keys', 6: 'origin', 7: 'autowrap', 12: 'cursor-blink',
            25: 'cursor-visible', 66: 'application-keypad', 69: 'left-right-margins',
            1000: 'mouse-press-release', 1002: 'mouse-button-motion', 1003: 'mouse-any-motion',
            1004: 'focus-events', 1005: 'mouse-utf8', 1006: 'mouse-sgr', 1007: 'alternate-scroll',
            1015: 'mouse-urxvt', 1049: 'alternate-screen-1049', 47: 'alternate-screen-47',
            1047: 'alternate-screen-1047', 2004: 'bracketed-paste', 2026: 'synchronized-output',
            45: 'reverse-wrap'},
    'ansi': {4: 'insert', 20: 'newline', 12: 'send-receive'},
}


def dumps(screen):
    out = ['warren-screen 1', 'size %d %d' % tuple(screen['size'])]
    c = screen['cursor']
    out.append('cursor %d %d shape=%d visible=%d pending-wrap=%d' % (
        c['row'], c['col'], c['shape'], c['visible'], c['pending_wrap']))
    out.append('region %d %d' % tuple(screen['region']))
    out.append('tabs ' + (','.join(str(t) for t in screen['tabs']) or '-'))
    out.append('title ' + (screen['title'] or '-'))
    for name in sorted(screen['modes']):
        out.append('mode %s %s' % (name, screen['modes'][name]))
    for number, row in enumerate(screen['rows'], 1):
        out.append('row %d extent=%d' % (number, screen['extents'][number - 1]))
        start = 0
        while start < len(row):
            end = start
            # Wide characters are never folded into a run: a run is one-cell-wide cells.
            while (row[start][0] == 1 and end + 1 < len(row) and row[end + 1] == row[start]):
                end += 1
            span = str(start + 1) if end == start else '%d-%d' % (start + 1, end + 1)
            out.append('%s %d %s %s' % (span, row[start][0], row[start][1], row[start][2]))
            start = end + 1
    return '\n'.join(out) + '\n'


def loads(text):
    lines = text.split('\n')
    if lines[0] != 'warren-screen 1' or lines[-1] != '':
        raise ValueError('not a warren-screen 1 dump')
    screen = {'modes': {}, 'rows': [], 'extents': []}
    for line in lines[1:-1]:
        f = line.split(' ')
        if f[0] == 'size':
            screen['size'] = [int(f[1]), int(f[2])]
        elif f[0] == 'cursor':
            keys = dict(item.split('=') for item in f[3:])
            screen['cursor'] = {'row': int(f[1]), 'col': int(f[2]), 'shape': int(keys['shape']),
                                'visible': int(keys['visible']),
                                'pending_wrap': int(keys['pending-wrap'])}
        elif f[0] == 'region':
            screen['region'] = [int(f[1]), int(f[2])]
        elif f[0] == 'tabs':
            screen['tabs'] = [] if f[1] == '-' else [int(t) for t in f[1].split(',')]
        elif f[0] == 'title':
            screen['title'] = '' if f[1] == '-' else f[1]
        elif f[0] == 'mode':
            screen['modes'][f[1]] = f[2] if f[2] == '?' else int(f[2])
        elif f[0] == 'row':
            if int(f[1]) != len(screen['rows']) + 1:
                raise ValueError('rows out of order at ' + line)
            screen['rows'].append([])
            screen['extents'].append(int(f[2].split('=')[1]))
        else:
            first, _, last = f[0].partition('-')
            first, last = int(first), int(last or first)
            row = screen['rows'][-1]
            if first != len(row) + 1 or len(f) != 4:
                raise ValueError('cells out of order at ' + line)
            row.extend([int(f[1]), f[2], f[3]] for _ in range(first, last + 1))
    cols, rows = screen['size']
    if len(screen['rows']) != rows or any(len(r) != cols for r in screen['rows']):
        raise ValueError('dump does not fill its size')
    return screen


def attr_set(attrs):
    return set() if attrs == '-' else set(attrs.split(','))


SHOWS_FOREGROUND = {'underline', 'double-underline', 'strike', 'inverse'}


def normalise(cell):
    """Normalisation N1 (blank-foreground): a blank cell with nothing that
    draws in the foreground colour is compared without its foreground. The
    reference emulator gives an erased cell the pen's foreground as well as
    its background, and resolves bold with a colour 0-7 to the bright colour
    there; nothing on the screen shows either."""
    if cell[1] != 'U+0020' or cell[2] == '-':
        return cell
    parts = cell[2].split(',')
    if SHOWS_FOREGROUND & set(parts):
        return cell
    return [cell[0], cell[1], ','.join(a for a in parts if not a.startswith('fg=')) or '-']


def compare(expected, got):
    """Every difference, each as (row name, detail). An empty list is a pass."""
    fails = []
    if expected['size'] != got['size']:
        return [('size', 'expected %s got %s' % (expected['size'], got['size']))]
    e, g = expected['cursor'], got['cursor']
    if (e['row'], e['col']) != (g['row'], g['col']):
        fails.append(('cursor-position', 'expected %d,%d got %d,%d' % (
            e['row'], e['col'], g['row'], g['col'])))
    for key, name in (('shape', 'cursor-shape'), ('visible', 'cursor-visible'),
                      ('pending_wrap', 'cursor-pending-wrap')):
        if e[key] != g[key]:
            fails.append((name, 'expected %s got %s' % (e[key], g[key])))
    for key in ('region', 'tabs', 'title'):
        if expected[key] != got[key]:
            fails.append((key, 'expected %s got %s' % (expected[key], got[key])))
    for name in sorted(set(expected['modes']) | set(got['modes'])):
        if expected['modes'].get(name) != got['modes'].get(name):
            fails.append(('mode', '%s expected %s got %s' % (
                name, expected['modes'].get(name), got['modes'].get(name))))
    for r, (ee, ge) in enumerate(zip(expected['extents'], got['extents']), 1):
        if ee != ge:
            fails.append(('row-extent', 'r%d expected %d got %d' % (r, ee, ge)))
    for r, (erow, grow) in enumerate(zip(expected['rows'], got['rows']), 1):
        for c, (ec, gc) in enumerate(zip(erow, grow), 1):
            ec, gc = normalise(ec), normalise(gc)
            where = 'r%dc%d' % (r, c)
            if ec[0] != gc[0]:
                kind = 'wide-continuation' if 0 in (ec[0], gc[0]) else 'cell-width'
                fails.append((kind, '%s expected width %d got %d' % (where, ec[0], gc[0])))
            if ec[1] != gc[1]:
                fails.append(('cell-character', '%s expected %s got %s' % (where, ec[1], gc[1])))
            if ec[2] != gc[2]:
                changed = sorted(attr_set(ec[2]) ^ attr_set(gc[2]))
                fails.append(('cell-attribute', '%s %s: expected %s got %s' % (
                    where, ' '.join(changed), ec[2], gc[2])))
    return fails


# The planted breaks. Each returns a changed copy and the row name that must go red.
def mutate_attribute(screen):
    s = copy.deepcopy(screen)
    for row in s['rows']:
        for cell in row:
            if cell[0] == 1 and cell[1] != 'U+0020':
                attrs = attr_set(cell[2])
                attrs ^= {'bold'}
                rest = sorted(a for a in attrs if '=' in a)
                plain = [a for a in ATTR_ORDER if a in attrs]
                cell[2] = ','.join(plain + [a for a in rest if a.startswith('fg=')] +
                                   [a for a in rest if a.startswith('bg=')]) or '-'
                return s, 'cell-attribute'
    raise ValueError('no written cell to mutate')


def mutate_cursor(screen):
    s = copy.deepcopy(screen)
    s['cursor']['col'] = s['cursor']['col'] % s['size'][0] + 1
    return s, 'cursor-position'


def mutate_continuation(screen):
    s = copy.deepcopy(screen)
    for row in s['rows']:
        for col, cell in enumerate(row):
            if cell[0] == 0:
                # What a broken emulator leaves: the lead cell still says wide,
                # the cell after it is an ordinary blank.
                row[col] = [1, 'U+0020', row[col][2]]
                return s, 'wide-continuation'
    raise ValueError('no wide character to mutate')


MUTATIONS = {'wrong-attribute': mutate_attribute, 'wrong-cursor-position': mutate_cursor,
             'dropped-wide-continuation': mutate_continuation}


def show(screen):
    """A short human reading of a dump: what is not default."""
    c = screen['cursor']
    out = ['cursor %d,%d shape=%d visible=%d pending-wrap=%d region=%d-%d title=%s' % (
        c['row'], c['col'], c['shape'], c['visible'], c['pending_wrap'],
        screen['region'][0], screen['region'][1],
        bytes.fromhex(screen['title']).decode('utf-8', 'replace'))]
    cols = screen['size'][0]
    if screen['size'] != [80, 24]:
        out.append('size %dx%d' % tuple(screen['size']))
    if screen['tabs'] != list(range(9, cols + 1, 8)):
        out.append('tabs ' + ','.join(str(t) for t in screen['tabs']))
    quiet = {'autowrap': 1, 'cursor-visible': 1, 'send-receive': 1, 'synchronized-output': '?'}
    odd = ['%s=%s' % (k, v) for k, v in sorted(screen['modes'].items()) if quiet.get(k, 0) != v]
    if odd:
        out.append('modes ' + ' '.join(odd))
    for number, row in enumerate(screen['rows'], 1):
        if screen['extents'][number - 1] == 0 and all(cell == [1, 'U+0020', '-'] for cell in row):
            continue
        text, notes, last = '', [], None
        for col, cell in enumerate(row, 1):
            if cell[0] == 0:
                text += '<'
            else:
                chars = ''.join(chr(min(int(p, 16), 0x10FFFF)) for p in cell[1].replace('U+', '').split('+'))
                chars = chars.encode('utf-8', 'replace').decode('utf-8')
                text += chars if chars != ' ' else ('_' if cell[2] != '-' else ' ')
            if cell[2] != last:
                if cell[2] != '-' or last is not None:
                    notes.append('%d:%s' % (col, cell[2]))
                last = cell[2]
        out.append('r%-2d ext=%-2d |%s|%s' % (number, screen['extents'][number - 1], text.rstrip(),
                                           ' ' + ' '.join(notes) if notes else ''))
    return '\n'.join(out)


def main(argv):
    if len(argv) >= 3 and argv[1] == 'show':
        for path in argv[2:]:
            print('== ' + path.rsplit('/', 1)[-1])
            print(show(loads(open(path).read())))
        return 0
    if len(argv) == 4 and argv[1] == 'compare':
        name = argv[3]
        fails = compare(loads(open(argv[2]).read()), loads(open(argv[3]).read()))
        for row, detail in fails:
            print('FAIL %s %s: %s' % (row, name, detail))
        if not fails:
            print('PASS screen ' + name)
        return 1 if fails else 0
    print('usage: screen.py compare EXPECTED GOT', file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv))
