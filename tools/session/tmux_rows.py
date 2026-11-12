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

Each client is a pty of the suite's own. Nothing is signalled: clients are
detached by tmux's own command and the server is ended with kill-server.
"""
import argparse
import fcntl
import os
from pathlib import Path
import pty
import select
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
                    'TERM': 'xterm-256color', 'TMUX_TMPDIR': str(out)}
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
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
