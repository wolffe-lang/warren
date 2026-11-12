#!/usr/bin/env python3
"""Drive the reference emulator headless: bytes in, a screen dump out.

  run.py dump INPUT [--cols N --rows N] [-o FILE]   one stream, one dump
  run.py cases DIR --out DIR                        every DIR/NAME.in against DIR/NAME.screen,
                                                    each dumped twice (determinism)
  run.py digests DIR --out DIR --manifest FILE      every stream in DIR dumped twice, the dump's
                                                    digest held to the manifest
  run.py selftest SCREEN...                         the planted mutations fail by name
  run.py mutations DIR --out DIR                    the same, on live dumps of DIR's cases

The emulator runs under a virtual X server and is only ever spoken to through
its pty (tools/oracle/feeder.py) and its print-screen file.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unicodedata

sys.path.insert(0, str(Path(__file__).resolve().parent))
import screen as S  # noqa: E402

HERE = Path(__file__).resolve().parent
RESOURCES = {
    'printAttributes': '2',        # print screen carries SGR, colours included
    'printerAutoClose': 'true',
    'printerExtent': 'true',       # the whole screen, not only the scroll region
    'precompose': 'false',         # combining characters stay as sent (normalisation N3)
    'checksumExtension': '22',     # DECRQCRA: no attributes, blanks counted, code point unmasked
    'allowWindowOps': 'true',      # CSI 21 t (title), CSI 18 t (size), CSI 8 t (resize)
    'allowTitleOps': 'true',
    'decTerminalID': '420',
    'utf8': '2',                   # always UTF-8; a stream cannot switch it off
    'utf8Title': 'true',
    'scrollBar': 'false',
    'cursorBlink': 'false',
    'bellIsUrgent': 'false',
    'visualBell': 'false',
}


class OracleError(Exception):
    pass


class Display:
    def __enter__(self):
        if os.environ.get('WARREN_ORACLE_DISPLAY'):
            self.proc, self.name = None, os.environ['WARREN_ORACLE_DISPLAY']
            return self
        read_fd, write_fd = os.pipe()
        self.proc = subprocess.Popen(
            ['Xvfb', '-displayfd', str(write_fd), '-screen', '0', '2560x1600x24', '-nolisten', 'tcp'],
            pass_fds=[write_fd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        os.close(write_fd)
        with os.fdopen(read_fd) as stream:
            number = stream.readline().strip()
        if not number:
            raise OracleError('the X server did not start')
        self.name = ':' + number
        return self

    def __exit__(self, *exc):
        if self.proc:
            self.proc.terminate()
            self.proc.wait()


def run_pass(display, which, source, cols, rows, work, extra=()):
    answers, printed = work / (which + '.json'), work / (which + '.print')
    for path in (answers, printed):
        if path.exists():
            path.unlink()
    command = ['xterm', '-u8', '-geometry', '%dx%d' % (cols, rows), '-fn', 'fixed',
               '-xrm', 'XTerm*printerCommand: cat > ' + str(printed)]
    for key, value in RESOURCES.items():
        command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
    command += ['-e', sys.executable, '-I', str(HERE / 'feeder.py'), which, str(source), str(answers)]
    command += [str(item) for item in extra]
    env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
           'HOME': str(work), 'TERM': 'xterm-256color',
           'WARREN_ORACLE_TIMEOUT': os.environ.get('WARREN_ORACLE_TIMEOUT', '20')}
    done = subprocess.run(command, env=env, capture_output=True, timeout=300)
    if done.returncode != 0 or not answers.exists():
        raise OracleError('pass %s: emulator exit %d: %s' % (
            which, done.returncode, done.stderr.decode('utf-8', 'replace')[-300:]))
    result = json.loads(answers.read_text())
    if 'error' in result:
        raise OracleError('pass %s: %s' % (which, result['error']))
    result['print'] = printed.read_bytes() if printed.exists() else b''
    return result


def sgr_to_attrs(params, state):
    """Apply one SGR, as the emulator prints it, to a state dict."""
    items = [p for p in params.split(';')] if params else ['0']
    for item in items:
        sub = item.split(':')
        code = int(sub[0] or 0)
        if code == 0:
            state.clear()
        elif code in (1, 2, 3, 4, 5, 7, 8, 9, 21):
            name = {1: 'bold', 2: 'dim', 3: 'italic', 4: 'underline', 5: 'blink', 7: 'inverse',
                    8: 'invisible', 9: 'strike', 21: 'double-underline'}[code]
            state[name] = True
        elif 30 <= code <= 37 or 40 <= code <= 47:
            state['fg' if code < 40 else 'bg'] = 'idx:%d' % (code % 10)
        elif 90 <= code <= 97 or 100 <= code <= 107:
            state['fg' if code < 100 else 'bg'] = 'idx:%d' % (code % 10 + 8)
        elif code in (38, 48):
            key = 'fg' if code == 38 else 'bg'
            if len(sub) >= 3 and sub[1] == '5':
                state[key] = 'idx:%d' % int(sub[2])
            elif len(sub) >= 5 and sub[1] == '2':
                state[key] = 'rgb:%d:%d:%d' % tuple(int(x or 0) for x in sub[-3:])
            else:
                raise OracleError('unreadable colour in print: ' + item)
        elif code in (39, 49):
            state.pop('fg' if code == 39 else 'bg', None)
        else:
            raise OracleError('unexpected SGR %d in print' % code)


def attrs_text(state):
    parts = [name for name in S.ATTR_ORDER if state.get(name)]
    parts += ['%s=%s' % (key, state[key]) for key in ('fg', 'bg') if key in state]
    return ','.join(parts) or '-'


def is_combining(cp):
    if cp > 0x10FFFF:
        return False
    ch = chr(cp)
    return unicodedata.combining(ch) != 0 or unicodedata.category(ch) in ('Mn', 'Me')


def decode(data):
    """UTF-8 to code points, as the emulator wrote it: it prints values past
    U+10FFFF and surrogates in the same form, which a strict decoder refuses."""
    out, at = [], 0
    while at < len(data):
        lead = data[at]
        size = 1 if lead < 0x80 else 2 if lead >> 5 == 6 else 3 if lead >> 4 == 14 else \
            4 if lead >> 3 == 30 else 5 if lead >> 2 == 62 else 6 if lead >> 1 == 126 else 0
        if size == 0 or at + size > len(data) or any(b >> 6 != 2 for b in data[at + 1:at + size]):
            raise OracleError('print screen wrote a byte that is not UTF-8: %r' % data[at:at + 4])
        cp = lead if size == 1 else lead & (0xFF >> (size + 1))
        for b in data[at + 1:at + size]:
            cp = cp << 6 | b & 0x3F
        out.append(cp)
        at += size
    return out


def parse_print(data, rows):
    """Rows of (code points, attrs) clusters, as print screen wrote them."""
    lines = data.split(b'\r\n')
    if lines and lines[-1] == b'':
        lines.pop()
    if len(lines) != rows:
        raise OracleError('print screen wrote %d rows for %d' % (len(lines), rows))
    result = []
    for raw in lines:
        line = decode(raw)
        clusters, state, at, stated = [], {}, 0, False
        while at < len(line):
            cp = line[at]
            if cp == 0x1b and at + 1 < len(line) and line[at + 1] == 0x23:
                at += 3                      # line width attribute; single width only
            elif cp == 0x1b and at + 1 < len(line) and line[at + 1] == 0x5b:
                end = line.index(0x6d, at)
                sgr_to_attrs(''.join(chr(c) for c in line[at + 2:end]), state)
                at = end + 1
                stated = True
            elif clusters and is_combining(cp):
                clusters[-1][0].append(cp)
                at += 1
            else:
                # The third field: a rendition was written just before this cell.
                clusters.append([[cp], attrs_text(state), stated])
                stated = False
                at += 1
        result.append(clusters)
    return result


def code_points(chars):
    return '+'.join('U+%04X' % cp for cp in chars)


REPLACEMENT = 'U+FFFD'


def lay_out(clusters, sums, limit):
    """Give print-screen clusters their columns, using the per-cell checksums.

    A cell holding code point N answers -N mod 65536. The second half of a
    wide character answers 0000, and so does the emulator's own replacement
    for a malformed byte (which print screen writes as '#'), and so does any
    code point whose low sixteen bits are zero. So the layout is searched for:
    every way of calling a cluster wide or narrow that explains every checksum,
    and there must be exactly one. Cells after the last cluster must be blank
    (FFE0). Returns cells for columns 1..limit (or fewer, if the row printed
    fewer)."""
    found = []

    def explains(chars, total):
        if total == '%04X' % ((-chars[0]) & 0xFFFF):
            return code_points(chars)
        if chars == [0x23] and total == '0000':
            return REPLACEMENT
        return None

    def search(index, col, cells):
        if len(found) > 1:
            return
        if index == len(clusters) or col >= limit:
            rest_blank = all(total == 'FFE0' for total in sums[col:]) if limit == len(sums) else True
            if index == len(clusters) and not rest_blank:
                return
            found.append(cells)
            return
        chars, attrs, stated = clusters[index]
        name = explains(chars, sums[col])
        if name is None:
            return
        search(index + 1, col + 1, cells + [[1, name, attrs, stated]])
        if col + 1 < len(sums) and sums[col + 1] == '0000' and name != REPLACEMENT:
            tail = [[0, '-', attrs, False]] if col + 1 < limit else []
            search(index + 1, col + 2, cells + [[2, name, attrs, stated]] + tail)

    search(0, 0, [])
    if len(found) != 1:
        raise OracleError('print and checksums %s: %s against %s' % (
            'disagree' if not found else 'have two readings',
            ' '.join(code_points(c[0]) for c in clusters[:12]), ' '.join(sums[:12])))
    return found[0]


def reply_field(text, head, tail):
    if not (text.startswith(head) and text.endswith(tail)):
        raise OracleError('unexpected answer %r' % text)
    return text[len(head):len(text) - len(tail)]


SEPARATOR_BG = ('bg=rgb:3:141:59', 'bg=rgb:59:141:3')


def describe(a):
    """Everything pass A's answers say, and its print laid out on the cells."""
    cols, rows = a['size']
    cursor_row, cursor_col = (int(x) for x in reply_field(a['cpr'], '\x1b[', 'R').split(';'))
    cir = reply_field(a['deccir'], '\x1bP1$u', '\x1b\\').split(';')
    shape = int(reply_field(a['decscusr'], '\x1bP1$r', ' q\x1b\\'))
    top, bottom = (int(x) for x in reply_field(a['decstbm'], '\x1bP1$r', 'r\x1b\\').split(';'))
    tabs = reply_field(a['dectabsr'], '\x1bP2$u', '\x1b\\')
    modes = {}
    for kind, head in (('dec', '\x1b[?'), ('ansi', '\x1b[')):
        for number, answer in a[kind + '_modes'].items():
            got_number, value = reply_field(answer, head, '$y').split(';')
            if got_number != number:
                raise OracleError('mode answer out of order: ' + answer)
            name = S.MODE_NAMES[kind][int(number)]
            modes[name] = {'1': 1, '3': 1, '2': 0, '4': 0}.get(value, '?')
    title = bytes.fromhex(a['title'])
    if not (title.startswith(b'\x1b]l') and title.endswith(b'\x1b\\')):
        raise OracleError('unexpected title answer')
    # The dump's cursor is absolute (DECCIR). CPR counts from the scroll
    # region's top under origin mode; the two must describe one cell.
    offset = top - 1 if modes['origin'] == 1 else 0
    if (int(cir[0]), int(cir[1])) != (cursor_row + offset, cursor_col):
        raise OracleError('CPR %r and DECCIR %r disagree on the cursor' % (a['cpr'], a['deccir']))
    screen = {'size': [cols, rows],
              'cursor': {'row': int(cir[0]), 'col': int(cir[1]), 'shape': shape,
                         'visible': modes['cursor-visible'],
                         'pending_wrap': 1 if ord(cir[5]) & 8 else 0},
              'region': [top, bottom], 'tabs': [int(t) for t in tabs.split('/') if t],
              'title': title[3:-2].hex(), 'modes': modes, 'rows': [], 'extents': []}
    printed = parse_print(a['print'], rows)
    for r in range(rows):
        cells = lay_out(printed[r], a['checksums'][r], cols)
        screen['extents'].append(len(cells))
        screen['rows'].append(cells)
    return screen


def colours(attrs):
    return [part for part in attrs.split(',') if '=' in part]


def finish(screen, a, s):
    """Replace pass A's renditions with pass S's, and hold the two together.

    Pass A's print does not state every cell's rendition (a plain cell after a
    bold one with the same colours gets no reset, and a never-written cell
    gets none at all), so its renditions are not used. Where it did write one
    outright before a character, pass S must agree."""
    cols, rows = screen['size']
    printed = parse_print(s['print'], rows)
    for r in range(rows):
        from_a = screen['rows'][r]
        # The original cells come first in the widened row; skip them. Past
        # pass A's extent they are blanks, one cluster each.
        skip = sum(1 for cell in from_a if cell[0] != 0) + cols - len(from_a)
        line = printed[r][skip:]
        row, at = [], 0
        for col in range(cols):
            if col < len(from_a) and from_a[col][0] == 0:
                row.append([0, '-', row[-1][2]])
                continue
            wide = col < len(from_a) and from_a[col][0] == 2
            if at + 1 >= len(line) or line[at][0] != [0x20] or line[at][1] != SEPARATOR_BG[(col + 1) % 2]:
                raise OracleError('row %d: pass S lost its separator before column %d' % (r + 1, col + 1))
            chars, attrs, _ = line[at + 1]
            if any(bg in attrs for bg in SEPARATOR_BG):
                raise OracleError('row %d column %d: the stream uses a separator colour' % (r + 1, col + 1))
            name = from_a[col][1] if col < len(from_a) else 'U+0020'
            if col >= len(from_a) and chars != [0x20]:
                raise OracleError('row %d: unprinted cell %d is not blank' % (r + 1, col + 1))
            if col < len(from_a) and name != REPLACEMENT and code_points(chars) != name:
                raise OracleError('row %d column %d: passes A and S disagree on the character' % (r + 1, col + 1))
            row.append([2 if wide else 1, name, attrs])
            at += 2
            if wide:                        # the filler in the second half's slot
                if at >= len(line) or line[at][0] != [0x20]:
                    raise OracleError('row %d: pass S lost the filler after column %d' % (r + 1, col + 1))
                at += 1
        if at != len(line):
            raise OracleError('row %d: pass S printed more than the screen' % (r + 1))
        # Where pass A wrote a rendition outright before a character, it is
        # that cell's own, and pass S must have read the same.
        for col, (cell_a, cell) in enumerate(zip(from_a, row)):
            if cell_a[3] and cell[1] != 'U+0020' and cell_a[2] != cell[2]:
                raise OracleError('row %d column %d: pass A printed %s, pass S %s' % (
                    r + 1, col + 1, cell_a[2], cell[2]))
        screen['rows'][r] = row
    return screen


def dump(display, source, cols, rows, work):
    work.mkdir(parents=True, exist_ok=True)
    a = run_pass(display, 'A', source, cols, rows, work)
    screen = describe(a)
    layout = work / 'continuation.json'
    layout.write_text(json.dumps([[col + 1 for col, cell in enumerate(row) if cell[0] == 0]
                                  for row in screen['rows']]))
    s = run_pass(display, 'S', source, cols, rows, work, extra=[layout])
    return finish(screen, a, s)


def case_size(path):
    """A recording carries its starting size; a raw stream is 80 by 24."""
    with path.open('rb') as stream:
        if stream.readline() == b'warren-rec 1\n':
            fields = stream.readline().split()
            return int(fields[1]), int(fields[2])
    return 80, 24


def cmd_cases(args):
    out = Path(args.out)
    failed = 0
    cases = sorted(Path(args.dir).glob('*.in'))
    if not cases:
        print('FAIL oracle-cases: no cases in ' + args.dir)
        return 1
    with Display() as display:
        for path in cases:
            name = path.stem
            cols, rows = case_size(path)
            try:
                first = dump(display, path, cols, rows, out / name / 'take-1')
                second = dump(display, path, cols, rows, out / name / 'take-2')
            except (OracleError, ValueError, subprocess.TimeoutExpired) as error:
                print('FAIL oracle-run %s: %s' % (name, error))
                failed += 1
                continue
            (out / name).mkdir(parents=True, exist_ok=True)
            (out / name / 'got.screen').write_text(S.dumps(first))
            if first != second:
                for row, detail in S.compare(first, second):
                    print('FAIL oracle-determinism %s %s: %s' % (name, row, detail))
                failed += 1
                continue
            if S.loads(S.dumps(first)) != first:
                print('FAIL dump-round-trip %s' % name)
                failed += 1
                continue
            expected_path = (Path(args.expected) / (name + '.screen') if args.expected
                             else path.with_suffix('.screen'))
            if args.write:
                expected_path.write_text(S.dumps(first))
                print('WROTE %s' % expected_path)
                continue
            if not expected_path.exists():
                print('FAIL oracle-case %s: no expected screen' % name)
                failed += 1
                continue
            fails = S.compare(S.loads(expected_path.read_text()), first)
            for row, detail in fails:
                print('FAIL %s %s: %s' % (row, name, detail))
            failed += bool(fails)
            if not fails:
                print('PASS oracle-case %s (two takes identical)' % name)
    print('oracle-cases: %d cases, %d failed' % (len(cases), failed))
    return 1 if failed else 0


def cmd_digests(args):
    """Every stream in DIR dumped twice; the dump's digest against a manifest."""
    import hashlib
    out = Path(args.out)
    manifest_path = Path(args.manifest)
    known = {}
    if manifest_path.exists() and not args.write:
        known = dict(line.split() for line in manifest_path.read_text().splitlines())
    streams = sorted(Path(args.dir).glob('*.in')) + sorted(Path(args.dir).glob('*.rec'))
    if not streams:
        print('FAIL oracle-digests: no streams in ' + args.dir)
        return 1
    failed, lines = 0, []
    with Display() as display:
        for path in streams:
            name = path.stem
            cols, rows = case_size(path)
            try:
                first = dump(display, path, cols, rows, out / name / 'take-1')
                second = dump(display, path, cols, rows, out / name / 'take-2')
            except (OracleError, ValueError, subprocess.TimeoutExpired) as error:
                print('FAIL oracle-run %s: %s' % (name, error))
                failed += 1
                continue
            text = S.dumps(first)
            (out / name / 'got.screen').write_text(text)
            if first != second:
                print('FAIL oracle-determinism %s: two takes differ' % name)
                failed += 1
                continue
            digest = hashlib.sha256(text.encode()).hexdigest()
            lines.append('%s %s' % (name, digest))
            if args.write:
                continue
            if known.get(name) != digest:
                print('FAIL oracle-digest %s: dump %s, manifest %s' % (name, digest, known.get(name)))
                failed += 1
    if args.write:
        manifest_path.write_text('\n'.join(lines) + '\n')
        print('WROTE %s (%d dumps)' % (manifest_path, len(lines)))
    missing = sorted(set(known) - {line.split()[0] for line in lines}) if not args.write else []
    for name in missing:
        print('FAIL oracle-digest %s: in the manifest, not dumped' % name)
    failed += len(missing)
    print('oracle-digests: %d streams, two takes each, %d failed' % (len(streams), failed))
    return 1 if failed else 0


def selftest(screens):
    """Every planted mutation must go red at its own row, on some screen."""
    failed = 0
    for name, text in screens:
        base = S.loads(text)
        if S.compare(base, base):
            print('FAIL harness-mutation identity: %s differs from itself' % name)
            failed += 1
    for mutation, make in S.MUTATIONS.items():
        seen = False
        for name, text in screens:
            base = S.loads(text)
            try:
                changed, row = make(base)
            except ValueError:
                continue
            seen = True
            rows = [r for r, _ in S.compare(base, changed)]
            # The dump's text form must carry the break too.
            rows_text = [r for r, _ in S.compare(base, S.loads(S.dumps(changed)))]
            if row in rows and row in rows_text:
                print('PASS harness-mutation %s on %s: red at %s' % (mutation, name, row))
            else:
                print('FAIL harness-mutation %s: not detected on %s (rows red: %s)' % (
                    mutation, name, ' '.join(rows) or 'none'))
                failed += 1
        if not seen:
            print('FAIL harness-mutation %s: no screen it applies to' % mutation)
            failed += 1
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('dump')
    p.add_argument('input')
    p.add_argument('--cols', type=int, default=80)
    p.add_argument('--rows', type=int, default=24)
    p.add_argument('-o', '--output')
    p.add_argument('--work')
    p = sub.add_parser('cases')
    p.add_argument('dir')
    p.add_argument('--out', required=True)
    p.add_argument('--expected', help='directory of NAME.screen (default: beside the cases)')
    p.add_argument('--write', action='store_true', help='record expected screens (review them)')
    p = sub.add_parser('digests')
    p.add_argument('dir')
    p.add_argument('--out', required=True)
    p.add_argument('--manifest', required=True)
    p.add_argument('--write', action='store_true')
    p = sub.add_parser('selftest')
    p.add_argument('screens', nargs='+')
    p = sub.add_parser('mutations')
    p.add_argument('dir')
    p.add_argument('--out', required=True)
    args = parser.parse_args()
    if args.command == 'cases':
        return cmd_cases(args)
    if args.command == 'digests':
        return cmd_digests(args)
    if args.command == 'selftest':
        return selftest([(Path(s).stem, Path(s).read_text()) for s in args.screens])
    if args.command == 'mutations':
        with Display() as display:
            screens = []
            for path in sorted(Path(args.dir).glob('*.in')):
                cols, rows = case_size(path)
                screens.append((path.stem, S.dumps(
                    dump(display, path, cols, rows, Path(args.out) / path.stem / 'mutations'))))
        return selftest(screens)
    with Display() as display:
        work = Path(args.work) if args.work else Path(tempfile.mkdtemp(prefix='oracle-'))
        text = S.dumps(dump(display, Path(args.input).resolve(), args.cols, args.rows, work))
    if args.output:
        Path(args.output).write_text(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except OracleError as error:
        print('FAIL oracle-run: %s' % error)
        sys.exit(1)
