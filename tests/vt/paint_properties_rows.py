#!/usr/bin/env python3
"""Background paint below the cursor and the resize properties (warren#31).

A row that holds only background paint (an erase under a coloured pen, nothing
written) counts as used in the properties checker's logical content, so the
lines down to it are compared. A resize keeps every line but lays paint only on
the row it sits on, clipped at the new width (paint is not content), so after a
narrowing resize that row may carry no paint and the comparison would stop at
the cursor: trailing lines with no content are not text and must not decide
R1. Each stream here is one of the nightly drive's seeds cut down to the
pieces that made the checker trap; each must pass the whole properties check
at 80x24. The controls are the same streams without the colour, and one with
text written below the paint.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
from corpus_properties import encode, observe  # noqa: E402

E = '\x1b['
CASES = {
    'painted-row-below-cursor-4397': E + '8;43f' + E + '43;48;5;183m' + E + '0K' + E + '36F',
    'painted-row-below-cursor-1164': (E + '48;2;47;95;142;94m' + E + '?1049h' + E + '?1049l' + E + '12;62H'
                                      + E + '31P' + E + '8;51H'),
    'painted-row-below-cursor-1726': E + '17;27H' + E + '7B' + E + '44;23;5m' + E + '0J' + E + '?1049l',
    'painted-row-below-cursor-2645': (E + '24;38;2;224;85;23;48;2;206;157;216m' + E + '?1049h' + E + '?1049l'
                                      + E + '20B' + E + '76P' + E + '?1049l'),
    'painted-row-below-cursor-4908': (E + '45;38;2;110;69;190m' + E + '?1049h' + E + '?1049l' + E + '20;54H'
                                      + E + '0K' + E + '1;11f'),
    'control-unpainted-4397': E + '8;43f' + E + '0K' + E + '36F',
    'control-unpainted-1726': E + '17;27H' + E + '7B' + E + '23;5m' + E + '0J' + E + '?1049l',
    'control-text-below-paint': E + '8;43f' + E + '44m' + E + '0K' + E + '49m' + E + '10;5Htext' + E + '36F',
}


def main():
    program = sys.argv[1]
    failed = 0
    for name, text in CASES.items():
        protocol, counts = encode([('size', (80, 24)), ('o', text.encode())])
        got, frame = observe(program, protocol, counts)
        if got.returncode or got.stderr or frame is None:
            where = got.stderr.decode('utf-8', 'replace').strip().splitlines()
            print('FAIL %s exit=%d %s' % (name, got.returncode, where[-1] if where else ''), flush=True)
            failed += 1
        else:
            print('PASS %s R1-R3-R8' % name, flush=True)
    print('PAINT-PROPERTIES cases=%d failed=%d' % (len(CASES), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
