#!/usr/bin/env python3
"""Record a program's terminal output on a pty of our own, inside the reference emulator.

  rec.py record --script FILE --out FILE [--cols N --rows N] -- COMMAND...
        starts a virtual X server and the reference emulator, and runs itself inside
  rec.py cat FILE            the output bytes alone
  rec.py info FILE           sizes, events, digest

The chain is: emulator <-> this recorder <-> a second pty <-> the program. The
emulator answers the program's queries (cursor position, device attributes),
so the program behaves as it does on a real terminal; the recorder logs every
byte the program writes and every resize.

A recording:
  warren-rec 1
  size COLS ROWS
  o N        N bytes of program output follow, then a newline
  i N        N bytes of scripted input follow, then a newline (not replayed)
  r COLS ROWS

A script, one step per line:
  quiet SECONDS      wait until the program has written nothing for that long
  send TEXT          bytes for the program; Python escapes (\\r, \\x1b) apply
  resize COLS ROWS
Signals are never sent: an interrupt is the byte \\x03 in a send.
"""
import argparse
import codecs
import fcntl
import hashlib
import os
from pathlib import Path
import pty
import select
import struct
import subprocess
import sys
import termios
import time
import tty

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'oracle'))


def set_size(fd, cols, rows):
    fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack('HHHH', rows, cols, 0, 0))


def inner(args):
    """Runs on the emulator's pty."""
    steps = [line.split(' ', 1) for line in Path(args.script).read_text().splitlines()
             if line and not line.startswith('#')]
    cols, rows = args.cols, args.rows
    log = open(args.out, 'wb')
    log.write(b'warren-rec 1\nsize %d %d\n' % (cols, rows))
    pending = bytearray()

    def flush():
        if pending:
            log.write(b'o %d\n' % len(pending) + bytes(pending) + b'\n')
            pending.clear()

    pid, master = pty.fork()
    if pid == 0:
        os.environ['TERM'] = 'xterm-256color'
        os.environ['COLORTERM'] = 'truecolor'
        os.execvp(args.command[0], args.command)
    set_size(master, cols, rows)
    old = termios.tcgetattr(0)
    tty.setraw(0)
    alive = True

    def pump(quiet, limit=30.0):
        """Copy both ways until the program is quiet for `quiet` seconds."""
        nonlocal alive
        last = time.monotonic()
        end = last + limit
        while alive and time.monotonic() - last < quiet and time.monotonic() < end:
            ready, _, _ = select.select([0, master], [], [], 0.02)
            if 0 in ready:                      # the emulator's answers
                os.write(master, os.read(0, 65536))
            if master in ready:
                try:
                    data = os.read(master, 65536)
                except OSError:
                    data = b''
                if not data:
                    alive = False
                    break
                pending.extend(data)
                os.write(1, data)
                last = time.monotonic()

    try:
        for verb, *rest in steps:
            arg = rest[0] if rest else ''
            if verb == 'quiet':
                pump(float(arg))
            elif verb == 'send':
                data = codecs.decode(arg, 'unicode_escape').encode('latin-1')
                flush()
                log.write(b'i %d\n' % len(data) + data + b'\n')
                if alive:
                    os.write(master, data)
            elif verb == 'resize':
                cols, rows = (int(x) for x in arg.split())
                flush()
                log.write(b'r %d %d\n' % (cols, rows))
                os.write(1, b'\x1b[8;%d;%dt' % (rows, cols))
                time.sleep(0.2)
                if alive:
                    set_size(master, cols, rows)
            else:
                raise ValueError('unknown step: ' + verb)
        pump(0.3, limit=5.0)
        flush()
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)
        log.close()
        os.close(master)


def events(path):
    data = Path(path).read_bytes()
    if not data.startswith(b'warren-rec 1\n'):
        raise ValueError('not a recording')
    at = len(b'warren-rec 1\n')
    while at < len(data):
        end = data.index(b'\n', at)
        f = data[at:end].split()
        at = end + 1
        if f[0] in (b'o', b'i'):
            yield f[0].decode(), data[at:at + int(f[1])]
            at += int(f[1]) + 1
        else:
            yield f[0].decode(), (int(f[1]), int(f[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='verb', required=True)
    for name in ('record', 'inner'):
        p = sub.add_parser(name)
        p.add_argument('--script', required=True)
        p.add_argument('--out', required=True)
        p.add_argument('--cols', type=int, default=80)
        p.add_argument('--rows', type=int, default=24)
        p.add_argument('command', nargs='+')
    for name in ('cat', 'info'):
        sub.add_parser(name).add_argument('file')
    args = parser.parse_args()
    if args.verb == 'inner':
        return inner(args)
    if args.verb == 'cat':
        for kind, value in events(args.file):
            if kind == 'o':
                sys.stdout.buffer.write(value)
        return 0
    if args.verb == 'info':
        counts = {'o': 0, 'i': 0, 'r': 0, 'size': 0}
        out_bytes = 0
        for kind, value in events(args.file):
            counts[kind] += 1
            out_bytes += len(value) if kind == 'o' else 0
        print('%s sha256=%s bytes=%d output=%d resizes=%d inputs=%d' % (
            Path(args.file).name, hashlib.sha256(Path(args.file).read_bytes()).hexdigest(),
            Path(args.file).stat().st_size, out_bytes, counts['r'], counts['i']))
        return 0
    import run as oracle
    with oracle.Display() as display:
        command = ['xterm', '-u8', '-geometry', '%dx%d' % (args.cols, args.rows), '-fn', 'fixed']
        for key, value in oracle.RESOURCES.items():
            command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
        command += ['-e', sys.executable, '-I', str(Path(__file__).resolve()), 'inner',
                    '--script', args.script, '--out', args.out,
                    '--cols', str(args.cols), '--rows', str(args.rows), '--'] + args.command
        env = dict(os.environ, DISPLAY=display.name, LC_ALL='C.UTF-8')
        return subprocess.run(command, env=env, timeout=600).returncode


if __name__ == '__main__':
    sys.exit(main())
