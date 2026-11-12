#!/usr/bin/env python3
"""A seeded stream of escape sequences inside the emulator's planned subset.

  fuzz.py SEED BYTES [--out FILE]      one stream
  fuzz.py --digests SEEDS BYTES        "seed sha256" per line, for the gate

The generator is its own (splitmix64), so a seed means the same stream on
every host and every Python. It draws only from what warren's first emulator
is meant to serve: text (ASCII, wide, combining), C0 controls, cursor motion,
erase, insert and delete, scroll regions, SGR with 256 and true colour, the
alternate screen, the mouse, paste and focus modes, titles, cursor shapes,
saved cursor, tab stops, and the status and attribute queries. Parameters
stray outside the screen on purpose; sequences are never malformed (that is a
separate, hostile corpus, and W1's).
"""
import argparse
import hashlib
import sys

MASK = (1 << 64) - 1


class Rng:
    def __init__(self, seed):
        self.state = seed & MASK

    def next(self):
        self.state = (self.state + 0x9E3779B97F4A7C15) & MASK
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & MASK
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & MASK
        return z ^ (z >> 31)

    def below(self, n):
        return self.next() % n

    def pick(self, items):
        return items[self.below(len(items))]


WIDE = ['中', '文', 'あ', 'Ａ', '한']
COMBINING = ['́', '̈', '⃗']
SGR = ['0', '1', '2', '3', '4', '5', '7', '8', '9', '22', '23', '24', '25', '27', '28', '29',
       '39', '49']
MODES = ['?1', '?6', '?7', '?25', '?1000', '?1002', '?1003', '?1004', '?1006', '?2004', '4']


def number(rng, limit):
    """Mostly on screen, sometimes zero, absent, or far outside."""
    kind = rng.below(10)
    if kind == 0:
        return ''
    if kind == 1:
        return '0'
    if kind == 2:
        return str(limit + rng.below(200))
    return str(1 + rng.below(limit))


def piece(rng, cols, rows):
    kind = rng.below(100)
    csi = '\x1b['
    if kind < 30:
        return ''.join(chr(0x20 + rng.below(0x5f)) for _ in range(1 + rng.below(24)))
    if kind < 35:
        return rng.pick(WIDE) * (1 + rng.below(3))
    if kind < 38:
        return chr(0x61 + rng.below(26)) + rng.pick(COMBINING)
    if kind < 46:
        return rng.pick(['\r', '\n', '\r\n', '\b', '\t', '\r\n'])
    if kind < 54:
        return csi + number(rng, rows) + ';' + number(rng, cols) + rng.pick('Hf')
    if kind < 62:
        return csi + number(rng, max(cols, rows)) + rng.pick('ABCDEFGd`')
    if kind < 67:
        return csi + rng.pick(['', '0', '1', '2']) + rng.pick('JK')
    if kind < 73:
        return csi + number(rng, cols) + rng.pick('@PXLM')
    if kind < 76:
        top = 1 + rng.below(rows)
        return csi + '%d;%dr' % (top, top + rng.below(rows))
    if kind < 86:
        parts = []
        for _ in range(1 + rng.below(3)):
            form = rng.below(8)
            if form == 0:
                parts.append('%d;5;%d' % (rng.pick([38, 48]), rng.below(256)))
            elif form == 1:
                parts.append('%d;2;%d;%d;%d' % (rng.pick([38, 48]), rng.below(256),
                                                rng.below(256), rng.below(256)))
            elif form == 2:
                parts.append(str(rng.pick([30, 40, 90, 100]) + rng.below(8)))
            else:
                parts.append(rng.pick(SGR))
        return csi + ';'.join(parts) + 'm'
    if kind < 89:
        return csi + rng.pick(MODES) + rng.pick('hl')
    if kind < 91:
        return csi + '?1049' + rng.pick('hl')
    if kind < 93:
        return rng.pick(['\x1b7', '\x1b8', '\x1bM', '\x1bD', '\x1bE', '\x1bH', csi + 'g',
                         csi + '3g'])
    if kind < 95:
        return csi + '%d q' % rng.below(7)
    if kind < 97:
        title = ''.join(chr(0x61 + rng.below(26)) for _ in range(1 + rng.below(8)))
        return '\x1b]' + rng.pick('02') + ';' + title + rng.pick(['\x07', '\x1b\\'])
    if kind < 99:
        return rng.pick([csi + 'c', csi + '5n', csi + '6n'])
    return rng.pick(['\x1b=', '\x1b>'])


def stream(seed, size, cols=80, rows=24):
    rng = Rng(seed)
    out = bytearray()
    while len(out) < size:
        out += piece(rng, cols, rows).encode('utf-8')
    return bytes(out)


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('seed')
    parser.add_argument('bytes', type=int)
    parser.add_argument('--out')
    parser.add_argument('--digests', action='store_true')
    parser.add_argument('--dir', help='with --digests: also write each stream as DIR/fuzz-SEED.in')
    args = parser.parse_args()
    if args.digests:
        for seed in range(1, int(args.seed) + 1):
            data = stream(seed, args.bytes)
            if args.dir:
                open('%s/fuzz-%04d.in' % (args.dir, seed), 'wb').write(data)
            print('%d %s' % (seed, hashlib.sha256(data).hexdigest()))
        return 0
    data = stream(int(args.seed), args.bytes)
    if args.out:
        open(args.out, 'wb').write(data)
    else:
        sys.stdout.buffer.write(data)
    return 0


if __name__ == '__main__':
    sys.exit(main())
