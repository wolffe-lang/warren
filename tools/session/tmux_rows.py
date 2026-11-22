#!/usr/bin/env python3
"""Session rows against tmux, the second black box. tmux is only ever run.

  tmux_rows.py --cases DIR --expected DIR --out DIR

Rows:
  tmux-identity        the pinned version answers
  tmux-pane-environment  what a program inside is told (TERM, TMUX, TMUX_PANE)
  tmux-screen NAME     a harness case fed to a pane: its text and cursor agree
                       with the reference emulator's expected screen
  tmux-shared-size     two clients of different sizes on one session: the
                       window's size under each `window-size` value
  tmux-split-sizes     a left-right split and a top-bottom split of the right
                       pane: each pane's size (tmux rounds the first half up,
                       warren down: 40/39 against 39/40 at 80 columns, named)
  tmux-zoom            the zoomed pane takes the whole window, and back
  tmux-focus-ring      which border cells tmux colours for the focused pane, with
                       three panes and with two (half the border), drawn by a
                       second tmux whose pane runs a client of the first; warren
                       draws the same cells (its frame-golden row)
  tmux-kill-pane       a killed pane's program has ended within a second
  tmux-missing-target  a split aimed at a session that does not exist is
                       refused with a non-zero exit and a reason, and no pane
                       is made or changed (warren: verb-refused-target)
  tmux-session-verbs   kill-session ends only its session, and a split with
                       -c DIR starts its program in DIR (warren:
                       kill-session-ends, split-in-dir; tmux prints a new
                       pane's id only with -P and runs a command through
                       sh -c, warren always prints it and runs argv as given)
  tmux-send-keys       every row of tests/session/send-keys.table, sent with
                       send-keys to a raw-mode reader in the row's mode,
                       reaches it as the table's tmux column (warren:
                       send-keys-bytes, to the warren column)
  tmux-capture         each case of tests/session/capture-cases, captured
                       with each flag set of tests/session/capture-goldens.json,
                       equals the golden's tmux text (warren: capture-cases)
  tmux-osc7            every row of tests/session/osc7.table: a pane that
                       printed OSC 7 for /tmp/osc7-base and then the row's
                       payload keeps the table's tmux column as #{pane_path}
                       (warren: src/osc7_table_test.lu, to the warren column)
  tmux-split-start     a pane reports a directory by OSC 7 in a session made
                       in another: split-window and new-window from a command
                       client start in the client's directory, split-window
                       from an attached (control-mode) client in the
                       session's, none in the reported one (warren:
                       split-starts-in-pane-cwd, a named difference)

Each client is a pty of the suite's own. Nothing is signalled: clients are
detached by tmux's own command and the server is ended with kill-server.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import pty
import select
import socket
import struct
import subprocess
import sys
import termios
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'oracle'))
import screen as S  # noqa: E402

TEXT_CASES = ['sgr', 'wide', 'erase', 'edit', 'scroll', 'pending-wrap']


class Tmux:
    def __init__(self, out, name):
        self.socket = str(out / (name + '.sock'))
        self.env = {'PATH': os.environ['PATH'], 'HOME': str(out), 'LC_ALL': 'C.UTF-8',
                    'TERM': 'xterm-256color', 'TMUX_TMPDIR': str(out), 'SHELL': '/bin/sh'}
        self.clients = []

    def run(self, *args, check=True):
        done = subprocess.run(['tmux', '-S', self.socket, '-f', '/dev/null', *args], env=self.env,
                              capture_output=True, text=True, timeout=30)
        if check and done.returncode != 0:
            raise RuntimeError('tmux %s: %s' % (' '.join(args), done.stderr.strip()))
        return done.stdout

    def attach(self, cols, rows):
        pid, fd = pty.fork()
        if pid == 0:
            os.execvpe('tmux', ['tmux', '-S', self.socket, '-f', '/dev/null', 'attach'], self.env)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))
        self.clients.append((pid, fd))
        self.drain(0.5)

    def drain(self, quiet):
        last = time.monotonic()
        while time.monotonic() - last < quiet:
            ready, _, _ = select.select([fd for _, fd in self.clients], [], [], 0.05)
            for fd in ready:
                try:
                    if os.read(fd, 65536):
                        last = time.monotonic()
                except OSError:
                    pass

    def close(self):
        self.run('kill-server', check=False)
        for pid, fd in self.clients:
            os.close(fd)
            os.waitpid(pid, 0)


def wait_for(tmux, target, text, limit=10.0):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if text in tmux.run('capture-pane', '-p', '-t', target):
            return
        time.sleep(0.05)
    raise RuntimeError('pane never showed ' + text)


def row_environment(out):
    tmux = Tmux(out, 'env')
    try:
        tmux.run('new-session', '-d', '-x', '80', '-y', '24',
                 'printf "TERM=%s TMUX=%s PANE=%s END\\n" "$TERM" "${TMUX:+set}" "$TMUX_PANE"; sleep 60')
        wait_for(tmux, '0', 'END')
        line = tmux.run('capture-pane', '-p', '-t', '0').splitlines()[0]
    finally:
        tmux.close()
    print('  measured: ' + line)
    want = 'TERM=tmux-256color TMUX=set PANE=%0 END'
    if line != want:
        print('FAIL tmux-pane-environment: got %r, expected %r' % (line, want))
        return 1
    print('PASS tmux-pane-environment')
    return 0


def row_screen(out, cases, expected, name):
    tmux = Tmux(out, 'screen-' + name)
    try:
        # The stream is followed by nothing: the pane's program then sleeps.
        tmux.run('new-session', '-d', '-x', '80', '-y', '24',
                 'cat %s; sleep 60' % (cases / (name + '.in')))
        time.sleep(0.6)
        text = tmux.run('capture-pane', '-p', '-t', '0').split('\n')[:24]
        cursor = tmux.run('display-message', '-p', '-t', '0', '#{cursor_y} #{cursor_x}').split()
    finally:
        tmux.close()
    want = S.loads((expected / (name + '.screen')).read_text())
    fails = []
    for number, row in enumerate(want['rows']):
        line = ''.join(chr(int(p, 16)) for cell in row if cell[0] != 0
                       for p in cell[1].replace('U+', '').split('+')).rstrip(' ')
        if text[number].rstrip(' ') != line:
            fails.append('row %d: tmux %r, reference %r' % (number + 1, text[number], line))
    got = (int(cursor[0]) + 1, int(cursor[1]) + 1)
    # Normalisation T1 (pending-wrap column): tmux reports a cursor waiting to
    # wrap as one column past the last; the reference reports the last column
    # and a flag.
    reference = (want['cursor']['row'], want['cursor']['col'] + want['cursor']['pending_wrap'])
    if got != reference:
        fails.append('cursor: tmux %s, reference %s' % (got, reference))
    for fail in fails:
        print('FAIL tmux-screen %s: %s' % (name, fail))
    if not fails:
        print('PASS tmux-screen %s (text and cursor agree with the reference)' % name)
    return 1 if fails else 0


def row_shared_size(out):
    tmux = Tmux(out, 'size')
    measured = {}
    try:
        tmux.run('new-session', '-d', '-x', '80', '-y', '24', 'sleep 60')
        tmux.attach(100, 30)
        tmux.attach(60, 20)
        for value in (None, 'smallest', 'largest'):
            if value:
                tmux.run('set-option', '-g', 'window-size', value)
                tmux.drain(0.5)
            name = value or 'default (%s)' % tmux.run('show-options', '-gv', 'window-size').strip()
            measured[name] = tmux.run('display-message', '-p', '-t', '0',
                                      '#{window_width}x#{window_height}').strip()
    finally:
        tmux.close()
    for name, size in measured.items():
        print('  measured: window-size %s -> %s' % (name, size))
    # One row of each client is tmux's status line.
    want = {'default (latest)': '60x19', 'smallest': '60x19', 'largest': '100x29'}
    if measured != want:
        print('FAIL tmux-shared-size: got %s, expected %s' % (measured, want))
        return 1
    print('PASS tmux-shared-size')
    return 0


def panes(tmux):
    out = tmux.run('list-panes', '-F', '#{pane_id} #{pane_left} #{pane_top} #{pane_width} #{pane_height} '
                   '#{pane_active} #{pane_pid} #{pane_current_command}')
    return [line.split() for line in out.splitlines() if line]


def row_split_sizes(out):
    tmux = Tmux(out, 'split')
    try:
        tmux.run('new-session', '-d', '-x', '80', '-y', '24', 'sleep 60')
        tmux.attach(80, 24)
        tmux.run('split-window', '-h', 'sleep 60')
        tmux.run('split-window', '-v', 'sleep 60')
        tmux.drain(0.3)
        sizes = ['%sx%s@%s,%s' % (p[3], p[4], p[1], p[2]) for p in panes(tmux)]
    finally:
        tmux.close()
    print('  measured: ' + ' '.join(sizes))
    want = ['40x23@0,0', '39x11@41,0', '39x11@41,12']
    if sizes != want:
        print('FAIL tmux-split-sizes: got %s, expected %s' % (sizes, want))
        return 1
    print('PASS tmux-split-sizes (warren: 39x22 and 40x22, then 40x10 and 40x11, by its own rule)')
    return 0


def row_zoom(out):
    tmux = Tmux(out, 'zoom')
    try:
        tmux.run('new-session', '-d', '-x', '80', '-y', '24', 'sleep 60')
        tmux.attach(80, 24)
        tmux.run('split-window', '-h', 'sleep 60')
        tmux.run('resize-pane', '-Z')
        tmux.drain(0.3)
        zoomed = [p[3] + 'x' + p[4] for p in panes(tmux) if p[5] == '1']
        tmux.run('resize-pane', '-Z')
        tmux.drain(0.3)
        back = [p[3] + 'x' + p[4] for p in panes(tmux) if p[5] == '1']
    finally:
        tmux.close()
    print('  measured: zoomed %s, back %s' % (zoomed, back))
    if zoomed != ['80x23'] or back != ['39x23']:
        print('FAIL tmux-zoom: zoomed %s back %s, expected 80x23 then 39x23' % (zoomed, back))
        return 1
    print('PASS tmux-zoom')
    return 0


def green_cells(styled_line):
    """The 1-based columns of a captured line drawn in foreground 32 (green)."""
    cols, col, fg, i = [], 0, None, 0
    while i < len(styled_line):
        ch = styled_line[i]
        if ch == '\x1b' and i + 1 < len(styled_line) and styled_line[i + 1] == '[':
            j = i + 2
            while j < len(styled_line) and not styled_line[j].isalpha():
                j += 1
            for part in (styled_line[i + 2:j] or '0').split(';'):
                if part in ('', '0', '39'):
                    fg = None
                elif part.isdigit() and (30 <= int(part) <= 37 or 90 <= int(part) <= 97):
                    fg = int(part)
            i = j + 1
            continue
        col += 1
        if fg == 32:
            cols.append(col)
        i += 1
    return cols


def ring(out, name, keys):
    """The green border cells after a layout and focus, as (col, row) pairs."""
    inner = Tmux(out, 'ring-' + name)
    outer = Tmux(out, 'outer-' + name)
    try:
        inner.run('new-session', '-d', '-s', 'r', '-x', '80', '-y', '24', 'sleep 60')
        # The client first, so that every split is made at the window it is drawn at.
        outer.run('new-session', '-d', '-x', '80', '-y', '24', 'tmux -S %s -f /dev/null attach -t r' % inner.socket)
        outer.run('set-option', '-g', 'status', 'off')
        time.sleep(0.6)
        for command in keys:
            inner.run(*command)
        time.sleep(0.8)
        styled = outer.run('capture-pane', '-p', '-e', '-t', '0').split('\n')[:23]
    finally:
        outer.close()
        inner.close()
    return [(c, r + 1) for r, line in enumerate(styled) for c in green_cells(line)]


def row_focus_ring(out):
    split3 = [('split-window', '-h', 'sleep 60'), ('split-window', '-v', 'sleep 60')]
    cases = {
        'three-left': (split3 + [('select-pane', '-t', '0')], [(41, r) for r in range(1, 24)]),
        'three-bottom-right': (split3, [(41, r) for r in range(12, 24)] + [(c, 12) for c in range(42, 81)]),
        'two-left': ([('split-window', '-h', 'sleep 60'), ('select-pane', '-t', '0')], [(41, r) for r in range(1, 13)]),
        'two-right': ([('split-window', '-h', 'sleep 60')], [(41, r) for r in range(13, 24)]),
    }
    failed = 0
    for name, (keys, want) in cases.items():
        got = ring(out, name, keys)
        if sorted(got) != sorted(want):
            print('FAIL tmux-focus-ring %s: green cells %s, expected %s' % (name, sorted(got), sorted(want)))
            failed += 1
        else:
            print('PASS tmux-focus-ring %s (%d cells)' % (name, len(want)))
    return 1 if failed else 0


def row_kill_pane(out):
    tmux = Tmux(out, 'kill')
    try:
        tmux.run('new-session', '-d', '-x', '80', '-y', '24', 'sleep 60')
        tmux.run('split-window', '-h', 'exec sleep 300')
        sleeper = [p for p in panes(tmux) if p[7] == 'sleep' and p[5] == '1'][0]
        pid = int(sleeper[6])
        tmux.run('kill-pane', '-t', sleeper[0])
        end = time.monotonic() + 1.0
        while time.monotonic() < end and Path('/proc/%d' % pid).exists():
            time.sleep(0.02)
        alive = Path('/proc/%d' % pid).exists()
    finally:
        tmux.close()
    if alive:
        print('FAIL tmux-kill-pane: the program %d outlived its pane by a second' % pid)
        return 1
    print('PASS tmux-kill-pane (the program ended; warren: close-hangs-up)')
    return 0


def row_missing_target(out):
    tmux = Tmux(out, 'target')
    try:
        tmux.run('new-session', '-d', '-s', 'work', '-x', '80', '-y', '24', 'sleep 60')
        before = panes(tmux)
        refused = subprocess.run(['tmux', '-S', tmux.socket, '-f', '/dev/null', 'split-window', '-h',
                                  '-t', 'nosuch:', 'sleep 60'],
                                 env=tmux.env, capture_output=True, text=True, timeout=30)
        after = panes(tmux)
    finally:
        tmux.close()
    reason = refused.stderr.strip()
    print('  measured: exit %d, %r, panes %s then %s' % (refused.returncode, reason, before, after))
    if refused.returncode == 0 or not reason or len(before) != 1 or after != before:
        print('FAIL tmux-missing-target: exit %d, reason %r, panes %d then %d, expected a non-zero exit with a '
              'reason and the one pane unchanged' % (refused.returncode, reason, len(before), len(after)))
        return 1
    print('PASS tmux-missing-target (warren: verb-refused-target, exit 1 naming no-such-session, the pane untouched)')
    return 0



def row_session_verbs(out):
    place = out / 'tmux-place'
    place.mkdir(parents=True, exist_ok=True)
    want_path = os.path.realpath(str(place))
    tmux = Tmux(out, 'sessions')
    try:
        tmux.run('new-session', '-d', '-s', 'a', '-x', '80', '-y', '24', 'sleep 60')
        tmux.run('new-session', '-d', '-s', 'b', '-x', '80', '-y', '24', 'sleep 60')
        tmux.run('kill-session', '-t', 'b')
        names = tmux.run('list-sessions', '-F', '#{session_name}').split()
        tmux.run('split-window', '-h', '-t', 'a:', '-c', str(place), 'sleep 60')
        paths = [line for line in tmux.run('list-panes', '-t', 'a:', '-F', '#{pane_current_path}').splitlines() if line]
    finally:
        tmux.close()
    print('  measured: sessions %s, pane paths %s' % (names, paths))
    if names != ['a'] or len(paths) != 2 or paths[1] != want_path:
        print('FAIL tmux-session-verbs: sessions %s, paths %s, expected [a] and the split in %s' % (names, paths, want_path))
        return 1
    print('PASS tmux-session-verbs (warren: kill-session-ends, split-in-dir)')
    return 0

SESSION = Path(__file__).resolve().parents[2] / 'tests' / 'session'

READER = r"""
import os, sys, tty
log, mode = sys.argv[1], sys.argv[2]
tty.setraw(0)
if mode in ("cursor", "keypad"):
    os.write(1, b"\x1b[?1h")
if mode == "keypad":
    os.write(1, b"\x1b=")
out = os.open(log, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
with open(log + ".ready", "w") as f:
    f.write("ready\n")
while True:
    try:
        b = os.read(0, 65536)
    except OSError:
        break
    if not b:
        break
    os.write(out, b)
"""


def log_size(path):
    try:
        return path.stat().st_size
    except OSError:
        return 0


def row_send_keys(out):
    reader = out / 'key-reader.py'
    reader.write_text(READER)
    sessions, logs, seen = {}, {}, {}
    fails = []
    try:
        for mode in ('normal', 'cursor', 'keypad'):
            t = Tmux(out, 'keys-' + mode)
            log = out / ('keys-' + mode + '.log')
            t.run('new-session', '-d', '-x', '80', '-y', '24', 'exec python3 -I %s %s %s' % (reader, log, mode))
            end = time.monotonic() + 10
            while not Path(str(log) + '.ready').exists() and time.monotonic() < end:
                time.sleep(0.05)
            time.sleep(0.3)
            sessions[mode], logs[mode], seen[mode] = t, log, 0
        for line in (SESSION / 'send-keys.table').read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):
                continue
            mode, args, tmux_hex, _warren, _why = line.split('\t')
            rc = sessions[mode].run('send-keys', '-t', '0', *json.loads(args), check=False)
            want = len(tmux_hex) // 2
            end = time.monotonic() + 2.0
            while log_size(logs[mode]) < seen[mode] + want and time.monotonic() < end:
                time.sleep(0.01)
            if want == 0:
                time.sleep(0.15)
            with open(logs[mode], 'rb') as f:
                f.seek(seen[mode])
                got = f.read(max(want, 0) or 64)
            got = got[:want] if want else got
            if got.hex() != tmux_hex:
                fails.append('%s %s: read %s, the table %s' % (mode, args, got.hex(), tmux_hex))
                break
            seen[mode] += want
        time.sleep(0.2)
        for mode, log in logs.items():
            if log_size(log) != seen[mode]:
                fails.append('%s: the reader read %d bytes, the table %d' % (mode, log_size(log), seen[mode]))
    finally:
        for t in sessions.values():
            t.close()
    for f in fails:
        print('FAIL tmux-send-keys ' + f)
    if not fails:
        print('PASS tmux-send-keys (%s)' % ' '.join('%s=%d' % kv for kv in sorted(seen.items())))
    return 1 if fails else 0


def row_capture(out):
    goldens = json.loads((SESSION / 'capture-goldens.json').read_text(encoding='utf-8'))
    fails, taken = [], 0
    for case, flag_sets in sorted(goldens.items()):
        t = Tmux(out, 'cap-' + case)
        try:
            t.run('new-session', '-d', '-x', '80', '-y', '24',
                  'cat %s; exec sleep 600' % (SESSION / 'capture-cases' / (case + '.in')))
            time.sleep(1.0)
            for flags, entry in sorted(flag_sets.items()):
                got = t.run('capture-pane', '-t', '0', *json.loads(flags))
                taken += 1
                if got != entry['tmux']:
                    fails.append('%s %s: %r, the golden %r' % (case, flags, got[:200], entry['tmux'][:200]))
        finally:
            t.close()
    for f in fails:
        print('FAIL tmux-capture ' + f)
    if not fails:
        print('PASS tmux-capture (%d captures)' % taken)
    return 1 if fails else 0


OSC7_PRINTER = ('import os, sys, time\n'
                'stem = sys.argv[1]\n'
                'def put(suffix):\n'
                '    with open(stem + suffix, "rb") as f:\n'
                '        sys.stdout.buffer.write(f.read())\n'
                '    sys.stdout.buffer.flush()\n'
                'put(".first")\n'
                'open(stem + ".one", "w").close()\n'
                'while not os.path.exists(stem + ".go"): time.sleep(0.02)\n'
                'put(".second")\n'
                'open(stem + ".two", "w").close()\n'
                'time.sleep(60)\n')
OSC7_SLEEPER = "python3 -I -c 'import time; time.sleep(60)'"


def osc7(body):
    return b'\x1b]7;' + body + b'\x07'


def osc7_expand(column, host):
    """An osc7.table column's bytes: hex, {host} this machine's name, {hh*N} byte hh N times."""
    out, i = bytearray(), 0
    while i < len(column):
        if column[i] == '{':
            j = column.index('}', i)
            token = column[i + 1:j]
            if token == 'host':
                out += host
            else:
                pair, n = token.split('*')
                out += bytes.fromhex(pair) * int(n)
            i = j + 1
        else:
            out += bytes.fromhex(column[i:i + 2])
            i += 2
    return bytes(out)


def wait_path(path, limit=10.0):
    end = time.monotonic() + limit
    while time.monotonic() < end:
        if path.exists():
            return True
        time.sleep(0.02)
    return False


def osc7_pane(t, out, name, first, second, cwd):
    """A detached session whose pane printed `first`, then, once told, `second`: its stem, or None."""
    stem = out / ('osc7-' + name)
    Path(str(stem) + '.first').write_bytes(first)
    Path(str(stem) + '.second').write_bytes(second)
    t.run('new-session', '-d', '-s', name, '-x', '80', '-y', '24', '-c', cwd,
          'python3 -I %s %s' % (out / 'osc7-printer.py', stem))
    if not wait_path(Path(str(stem) + '.one')):
        return None
    time.sleep(0.4)
    Path(str(stem) + '.go').touch()
    if not wait_path(Path(str(stem) + '.two')):
        return None
    time.sleep(0.4)
    return stem


def row_osc7(out):
    (out / 'osc7-printer.py').write_text(OSC7_PRINTER)
    host = socket.gethostname().encode()
    base = b'file:///tmp/osc7-base'
    t = Tmux(out, 'osc7')
    fails, rows = [], 0
    try:
        for line in (SESSION / 'osc7.table').read_text(encoding='utf-8').splitlines():
            if not line or line.startswith('#'):
                continue
            case, payload, tmux_column, _warren, _why = line.split('\t')
            name = 'c%d' % rows
            if osc7_pane(t, out, name, osc7(base), osc7_expand(payload, host), '/') is None:
                fails.append('%s: the pane did not print' % case)
                break
            got = t.run('display-message', '-p', '-t', name, '#{pane_path}').rstrip('\n').encode()
            want = base if tmux_column == 'kept' else (b'' if tmux_column == 'none' else osc7_expand(tmux_column, host))
            if got != want:
                fails.append('%s: pane_path %r, the table %r' % (case, got[:80], want[:80]))
            t.run('kill-session', '-t', name, check=False)
            rows += 1
    except (RuntimeError, subprocess.TimeoutExpired) as e:
        fails.append(str(e))
    finally:
        t.close()
    for f in fails:
        print('FAIL tmux-osc7 ' + f)
    if not fails:
        print('PASS tmux-osc7 rows=%d' % rows)
    return 1 if fails else 0


def row_split_start(out):
    (out / 'osc7-printer.py').write_text(OSC7_PRINTER)
    fails = []
    for how in ('split-command', 'window-command', 'split-control'):
        dirs = {k: out / ('start-%s-%s' % (how, k)) for k in ('session', 'osc7', 'caller')}
        for d in dirs.values():
            d.mkdir(parents=True, exist_ok=True)
        t = Tmux(out, 'start-' + how)
        try:
            if osc7_pane(t, out, how, osc7(b'file://' + str(dirs['osc7']).encode()), b'', str(dirs['session'])) is None:
                fails.append('%s: the pane did not print' % how)
                continue
            if how == 'split-command':
                subprocess.run(['tmux', '-S', t.socket, '-f', '/dev/null', 'split-window', '-t', how, OSC7_SLEEPER],
                               env=t.env, cwd=str(dirs['caller']), capture_output=True, timeout=30, check=True)
            elif how == 'window-command':
                subprocess.run(['tmux', '-S', t.socket, '-f', '/dev/null', 'new-window', '-t', how, OSC7_SLEEPER],
                               env=t.env, cwd=str(dirs['caller']), capture_output=True, timeout=30, check=True)
            else:
                subprocess.run(['tmux', '-S', t.socket, '-f', '/dev/null', '-C', 'attach-session', '-t', how],
                               env=t.env, cwd=str(dirs['caller']), capture_output=True, timeout=30,
                               input=('split-window "%s"\ndetach-client\n' % OSC7_SLEEPER).encode())
            time.sleep(0.6)
            panes = t.run('list-panes', '-s', '-t', how, '-F', '#{pane_current_path}').splitlines()
            reported = t.run('display-message', '-p', '-t', how + ':0.0', '#{pane_path}').strip()
            want = str(dirs['session'] if how == 'split-control' else dirs['caller'])
            if len(panes) != 2 or panes[1] != want or str(dirs['osc7']) in panes[1:]:
                fails.append('%s: the new pane is in %s, not %s' % (how, panes[1:], want))
            if reported != 'file://' + str(dirs['osc7']):
                fails.append('%s: the first pane reported %r' % (how, reported))
        except (RuntimeError, subprocess.SubprocessError) as e:
            fails.append('%s: %s' % (how, e))
        finally:
            t.close()
    for f in fails:
        print('FAIL tmux-split-start ' + f)
    if not fails:
        print('PASS tmux-split-start (split and new window from a command: the caller\'s; from a client: the session\'s)')
    return 1 if fails else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cases', type=Path, required=True)
    parser.add_argument('--expected', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(['tmux', '-V'], capture_output=True, text=True).stdout.strip()
    failed = 0
    if version != 'tmux 3.4':
        print('FAIL tmux-identity: ' + version)
        failed += 1
    else:
        print('PASS tmux-identity ' + version)
    failed += row_environment(args.out)
    for name in TEXT_CASES:
        failed += row_screen(args.out, args.cases, args.expected, name)
    failed += row_shared_size(args.out)
    failed += row_split_sizes(args.out)
    failed += row_zoom(args.out)
    failed += row_focus_ring(args.out)
    failed += row_kill_pane(args.out)
    failed += row_missing_target(args.out)
    failed += row_session_verbs(args.out)
    failed += row_send_keys(args.out)
    failed += row_capture(args.out)
    failed += row_osc7(args.out)
    failed += row_split_start(args.out)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
