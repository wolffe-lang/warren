#!/usr/bin/env python3
"""The capture rows' checks: what `warren capture-pane` printed, held to the reference emulator's expected screen
(the same screens tmux-screen holds tmux to) or to a golden text.

  capture_check.py screen CAPTURE EXPECTED.screen     -p: one line a row, each the row's text, trailing blanks dropped
  capture_check.py escapes CAPTURE EXPECTED.screen    -e: read as cells, each captured cell's text and rendition
                                                      equal the screen's (N1 as the oracle normalises it), and every
                                                      cell past a line's end is blank
  capture_check.py golden CAPTURE GOLDEN              byte for byte
  capture_check.py case CAPTURE GOLDENS CASE FLAGS    the warren column of tests/session/capture-goldens.json,
                                                      byte for byte (FLAGS as the JSON list of the flags)
  capture_check.py case-spans CAPTURE GOLDENS CASE FLAGS  the same, read as cells (the -e cases: equal spans)

Prints PASS or FAIL with the first differences; exits 1 on a FAIL.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools' / 'oracle'))
import screen as S  # noqa: E402

FLAGS = {1: 'bold', 2: 'dim', 3: 'italic', 4: 'underline', 21: 'double-underline', 5: 'blink', 7: 'inverse',
         8: 'invisible', 9: 'strike'}
OFF = {22: ('bold', 'dim'), 23: ('italic',), 24: ('underline', 'double-underline'), 25: ('blink',), 27: ('inverse',),
       28: ('invisible',), 29: ('strike',)}


def row_text(row):
    return ''.join(chr(int(p, 16)) for cell in row if cell[0] != 0
                   for p in cell[1].replace('U+', '').split('+')).rstrip(' ')


def colour(params, i):
    """A 38/48 colour at params[i] (the 38 or 48): (text, next index)."""
    if i + 1 < len(params) and params[i + 1] == '5' and i + 2 < len(params):
        return 'idx:%d' % int(params[i + 2]), i + 3
    if i + 1 < len(params) and params[i + 1] == '2' and i + 4 < len(params):
        return 'rgb:%d:%d:%d' % tuple(int(x) for x in params[i + 2:i + 5]), i + 5
    return None, len(params)


def apply_sgr(state, body):
    params = body.split(';') if body else ['0']
    i = 0
    while i < len(params):
        p = params[i]
        if p in ('', '0'):
            state['flags'] = set(); state['fg'] = None; state['bg'] = None
        elif p == '4:2':
            state['flags'].add('double-underline')
        elif p.startswith('4:'):
            state['flags'].discard('double-underline'); state['flags'].discard('underline')
            if p != '4:0': state['flags'].add('underline')
        elif p.isdigit():
            n = int(p)
            if n in FLAGS: state['flags'].add(FLAGS[n])
            elif n in OFF:
                for f in OFF[n]: state['flags'].discard(f)
            elif 30 <= n <= 37: state['fg'] = 'idx:%d' % (n - 30)
            elif 90 <= n <= 97: state['fg'] = 'idx:%d' % (n - 82)
            elif 40 <= n <= 47: state['bg'] = 'idx:%d' % (n - 40)
            elif 100 <= n <= 107: state['bg'] = 'idx:%d' % (n - 92)
            elif n == 39: state['fg'] = None
            elif n == 49: state['bg'] = None
            elif n in (38, 48):
                c, j = colour(params, i)
                state['fg' if n == 38 else 'bg'] = c
                i = j
                continue
        i += 1


def attrs_of(state):
    parts = [a for a in S.ATTR_ORDER if a in state['flags']]
    if state['fg']: parts.append('fg=' + state['fg'])
    if state['bg']: parts.append('bg=' + state['bg'])
    return ','.join(parts) or '-'


def styled_rows(text):
    """Each captured line as (scalar, attrs) pairs, the pen carried from line to line."""
    state = {'flags': set(), 'fg': None, 'bg': None}
    rows = []
    for line in text.split('\n')[:-1]:
        cells, i = [], 0
        while i < len(line):
            if line[i] == '\x1b' and i + 1 < len(line) and line[i + 1] == '[':
                j = i + 2
                while j < len(line) and not ('@' <= line[j] <= '~'):
                    j += 1
                if j < len(line) and line[j] == 'm':
                    apply_sgr(state, line[i + 2:j])
                i = j + 1
                continue
            cells.append((line[i], attrs_of(state)))
            i += 1
        rows.append(cells)
    return rows


def check_screen(capture, expected):
    want = S.loads(expected.read_text())
    lines = capture.read_text(encoding='utf-8').split('\n')
    fails = []
    if lines[-1] != '' or len(lines) - 1 != len(want['rows']):
        fails.append('%d lines, the pane has %d rows' % (len(lines) - 1, len(want['rows'])))
    for n, row in enumerate(want['rows']):
        got = lines[n] if n < len(lines) else ''
        if got != row_text(row):
            fails.append('row %d: captured %r, the screen %r' % (n + 1, got, row_text(row)))
    return fails


def check_escapes(capture, expected):
    want = S.loads(expected.read_text())
    got_rows = styled_rows(capture.read_text(encoding='utf-8'))
    fails = []
    if len(got_rows) != len(want['rows']):
        fails.append('%d lines, the pane has %d rows' % (len(got_rows), len(want['rows'])))
    for n, row in enumerate(want['rows']):
        got = got_rows[n] if n < len(got_rows) else []
        cells = [S.normalise(c) for c in row if c[0] != 0]
        k = 0
        for cell in cells:
            scalars = [chr(int(p, 16)) for p in cell[1].replace('U+', '').split('+')]
            if k >= len(got):
                if cell[1] != 'U+0020':
                    fails.append('row %d: %r not captured' % (n + 1, ''.join(scalars)))
                    break
                continue
            text = ''.join(ch for ch, _ in got[k:k + len(scalars)])
            attrs = got[k][1]
            normal = S.normalise([cell[0], cell[1], attrs])[2]
            if text != ''.join(scalars) or S.attr_set(normal) != S.attr_set(cell[2]):
                fails.append('row %d cell %d: captured %r %s, the screen %r %s' % (n + 1, k + 1, text, normal, ''.join(scalars), cell[2]))
                break
            k += len(scalars)
    return fails


def main():
    mode, capture, other = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
    if mode == 'screen':
        fails = check_screen(capture, other)
    elif mode == 'escapes':
        fails = check_escapes(capture, other)
    elif mode in ('case', 'case-spans'):
        import json
        goldens = json.loads(other.read_text(encoding='utf-8'))
        entry = goldens[sys.argv[4]][sys.argv[5]]
        got = capture.read_text(encoding='utf-8')
        if mode == 'case':
            fails = [] if got == entry['warren'] else ['captured %r, the golden %r (%s)' % (got[:300], entry['warren'][:300], entry['difference'])]
        else:
            a, b = styled_rows(got), styled_rows(entry['warren'])
            fails = [] if a == b else ['spans differ: captured %r, the golden %r' % (got[:300], entry['warren'][:300])]
    elif mode == 'golden':
        a, b = capture.read_bytes(), other.read_bytes()
        fails = [] if a == b else ['%d bytes, the golden %d; first difference at byte %d' % (
            len(a), len(b), next((i for i in range(min(len(a), len(b))) if a[i] != b[i]), min(len(a), len(b))))]
    else:
        fails = ['unknown mode ' + mode]
    for f in fails[:5]:
        print('FAIL ' + f)
    if not fails:
        print('PASS ' + mode)
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
