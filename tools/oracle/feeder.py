#!/usr/bin/env python3
"""Runs inside the reference emulator, on its pty: replay a stream, then ask.

The emulator is a black box. Everything this program learns, it learns by
writing bytes to the terminal and reading the terminal's own answers:

  cursor position           CPR      CSI 6 n
  cursor state, wrap flag   DECCIR   CSI 1 $ w
  tab stops                 DECTABSR CSI 2 $ w
  cursor shape              DECRQSS  DCS $ q SP q ST
  scroll region             DECRQSS  DCS $ q r ST
  modes                     DECRQM   CSI ? Ps $ p  and  CSI Ps $ p
  title                     CSI 21 t
  size                      CSI 18 t
  one cell's code point     DECRQCRA CSI Pid ; 1 ; r ; c ; r ; c * y
  rows with their SGR       MC       CSI i  (print screen, to a file)

Pass A asks all of it. Its print screen has two limits: a row stops at its
last written cell, and a cell with no rendition of its own that follows a
cell with one is printed without a reset when the colours are the same. So
pass S replays the same bytes in a fresh emulator and spreads the screen out
(see pass_spread) until print screen has to state every cell's rendition.
"""
import json
import os
import select
import sys
import termios
import time
import tty

DEC_MODES = [1, 6, 7, 12, 25, 45, 47, 66, 69, 1000, 1002, 1003, 1004, 1005, 1006,
             1007, 1015, 1047, 1049, 2004, 2026]
ANSI_MODES = [4, 12, 20]
SENTINEL = 9731


class Tty:
    def __init__(self, timeout):
        self.fd = 0
        self.timeout = timeout
        self.pending = b''

    def read_until(self, done):
        end = time.monotonic() + self.timeout
        while not done(self.pending):
            left = end - time.monotonic()
            if left <= 0:
                raise TimeoutError('no answer from the emulator; had %r' % self.pending[-80:])
            ready, _, _ = select.select([self.fd], [], [], left)
            if ready:
                chunk = os.read(self.fd, 65536)
                if not chunk:
                    raise EOFError('terminal closed')
                self.pending += chunk
        got, self.pending = self.pending, b''
        return got

    def write(self, data):
        view = memoryview(data)
        while view:
            # Answers to queries inside the replayed stream must not fill the
            # pty's input queue while we are still writing.
            ready_r, ready_w, _ = select.select([self.fd], [1], [], self.timeout)
            if ready_r:
                self.pending += os.read(self.fd, 65536)
            if ready_w:
                view = view[os.write(1, view[:4096]):]
            if not ready_r and not ready_w:
                raise TimeoutError('emulator stopped reading')

    def sync(self):
        """Everything written so far has been processed once this returns."""
        marker = b'\x1bP%d!~' % SENTINEL
        self.write(b'\x1b[%d;1;1;1;1;1*y' % SENTINEL)
        self.read_until(lambda b: marker in b and b.endswith(b'\x1b\\'))

    def ask(self, query, final):
        self.write(query)
        return self.read_until(lambda b: b.endswith(final))


def replay(term, events):
    for event in events:
        if event[0] == 'o':
            term.write(event[1])
        elif event[0] == 'r':
            term.sync()
            term.write(b'\x1b[8;%d;%dt' % (event[2], event[1]))
            deadline = time.monotonic() + term.timeout
            while size_of(term) != (event[1], event[2]):
                if time.monotonic() > deadline:
                    raise TimeoutError('the emulator did not take the new size')
                time.sleep(0.01)
    term.sync()
    term.pending = b''


def load(path):
    """A raw byte file, or a recording (see tools/corpus/rec.py)."""
    data = open(path, 'rb').read()
    if not data.startswith(b'warren-rec 1\n'):
        return [('o', data)]
    events, at = [], len(b'warren-rec 1\n')
    while at < len(data):
        line_end = data.index(b'\n', at)
        fields = data[at:line_end].split()
        at = line_end + 1
        if fields[0] in (b'o', b'i'):
            size = int(fields[1])
            if fields[0] == b'o':
                events.append(('o', data[at:at + size]))
            at += size + 1
        elif fields[0] == b'r':
            events.append(('r', int(fields[1]), int(fields[2])))
        elif fields[0] != b'size':
            raise ValueError('bad recording line: %r' % fields)
    return events


def size_of(term):
    answer = term.ask(b'\x1b[18t', b't')
    rows, cols = answer[answer.rindex(b'\x1b[8;') + 4:-1].split(b';')
    return int(cols), int(rows)


def pass_a(term, out):
    result = {'pass': 'A'}
    st = b'\x1b\\'
    cols, rows = size_of(term)
    result['size'] = [cols, rows]
    result['cpr'] = term.ask(b'\x1b[6n', b'R').decode('latin-1')
    result['deccir'] = term.ask(b'\x1b[1$w', st).decode('latin-1')
    result['dectabsr'] = term.ask(b'\x1b[2$w', st).decode('latin-1')
    result['decscusr'] = term.ask(b'\x1bP$q q\x1b\\', st).decode('latin-1')
    result['decstbm'] = term.ask(b'\x1bP$qr\x1b\\', st).decode('latin-1')
    result['dec_modes'] = {str(m): term.ask(b'\x1b[?%d$p' % m, b'$y').decode('latin-1')
                           for m in DEC_MODES}
    result['ansi_modes'] = {str(m): term.ask(b'\x1b[%d$p' % m, b'$y').decode('latin-1')
                            for m in ANSI_MODES}
    result['title'] = term.ask(b'\x1b[21t', st).hex()
    # Everything that describes state is recorded. DECRQCRA counts rows from
    # the scroll region under origin mode, so leave it before asking for cells.
    term.write(b'\x1b[?6l\x1b[?69l')
    # One request per cell. The emulator answers in order, so write a row of
    # requests and read a row of answers.
    sums = []
    for row in range(1, rows + 1):
        term.write(b''.join(b'\x1b[%d;1;%d;%d;%d;%d*y' % (col, row, col, row, col)
                            for col in range(1, cols + 1)))
        last = b'\x1bP%d!~' % cols
        answer = term.read_until(lambda b: b.endswith(st) and b.count(st) >= cols and last in b)
        parts = [p for p in answer.split(st) if p]
        if len(parts) != cols:
            raise ValueError('row %d: %d checksum answers for %d cells' % (row, len(parts), cols))
        line = []
        for col, part in enumerate(parts, 1):
            head = b'\x1bP%d!~' % col
            if not part.startswith(head):
                raise ValueError('row %d: answer out of order at column %d' % (row, col))
            line.append(part[len(head):].decode('ascii'))
        sums.append(line)
    result['checksums'] = sums
    term.write(b'\x1b[i')
    term.sync()
    json.dump(result, open(out, 'w'))


SEPARATORS = (b'\x1b[0;48;2;3;141;59m', b'\x1b[0;48;2;59;141;3m')


def pass_spread(term, out, layout):
    """Make print screen state every cell's rendition.

    The screen is widened to twice its columns. Working from the right, each
    cell (a wide character as its pair) is copied to twice its column with
    DECCRA, and the column before it gets a separator: a blank on a background
    no stream uses, alternating between two so that neighbours differ. Print
    screen writes a rendition whenever the colours change, so every copied
    cell is printed with its own."""
    cols, rows = size_of(term)
    continuation = json.load(open(layout))
    term.write(b'\x1b[?6l\x1b[?69l\x1b[4l\x1b[?7h\x1b[r')
    term.write(b'\x1b[8;%d;%dt' % (rows, 2 * cols))
    deadline = time.monotonic() + term.timeout
    while size_of(term) != (2 * cols, rows):
        if time.monotonic() > deadline:
            raise TimeoutError('the emulator did not widen')
        time.sleep(0.01)
    for row in range(1, rows + 1):
        skip = set(continuation[row - 1])
        chunk = []
        for col in range(cols, 0, -1):
            if col in skip:
                continue
            last = col + 1 if col + 1 in skip else col
            chunk.append(b'\x1b[%d;%d;%d;%d;1;%d;%d;1$v' % (row, col, row, last, row, 2 * col))
            chunk.append(SEPARATORS[col % 2] + b'\x1b[%d;%dH \x1b[0m' % (row, 2 * col - 1))
            if last != col:                 # the slot of the skipped second half
                chunk.append(SEPARATORS[col % 2] + b'\x1b[%d;%dH \x1b[0m' % (row, 2 * col + 2))
        term.write(b''.join(chunk))
    term.write(b'\x1b[i')
    term.sync()
    json.dump({'pass': 'S', 'size': [cols, rows]}, open(out, 'w'))


def main():
    which, source, out = sys.argv[1:4]
    old = termios.tcgetattr(0)
    tty.setraw(0)
    try:
        term = Tty(timeout=float(os.environ.get('WARREN_ORACLE_TIMEOUT', '20')))
        replay(term, load(source))
        if which == 'A':
            pass_a(term, out)
        else:
            pass_spread(term, out, sys.argv[4])
    except Exception as error:  # the driver reads this file, never our stderr
        json.dump({'error': '%s: %s' % (type(error).__name__, error)}, open(out, 'w'))
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)


if __name__ == '__main__':
    main()
