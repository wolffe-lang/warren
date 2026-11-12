#!/usr/bin/env python3
"""The harness's own small cases: one stream each, written out as NAME.in.

These prove the dump mechanism, not an emulator. Each stream sets a title and a
cursor shape so that no expectation rests on the reference emulator's defaults.
"""
from pathlib import Path
import sys

E = b'\x1b'
HEAD = E + b']2;t\x07' + E + b'[2 q'
CASES = {
    # One cell per rendition, then every colour form.
    'sgr': HEAD + b'A' + E + b'[1mB' + E + b'[0;2mC' + E + b'[0;3mD' + E + b'[0;4mE' + E + b'[0;5mF'
           + E + b'[0;7mG' + E + b'[0;8mH' + E + b'[0;9mI' + E + b'[0;31mJ' + E + b'[0;92mK'
           + E + b'[0;38;5;196mL' + E + b'[0;48;2;1;2;3mM'
           + E + b'[0;1;4;38;2;10;20;30;48;5;17mN' + E + b'[0m',
    # A wide character, a combining mark, and a wide character that does not
    # fit in the last column (it wraps whole).
    'wide': HEAD + b'A\xe4\xb8\xadBe\xcc\x81C' + E + b'[2;79HX\xe6\x96\x87',
    # Erase with a background colour: to end of line, a whole line, and a
    # written space beside erased cells. Then the cursor parked mid-screen.
    'erase': HEAD + E + b'[41m' + E + b'[K' + E + b'[0m' + E + b'[1;3H ' + E + b'[2;1Habc'
             + E + b'[42m' + E + b'[2;2H' + E + b'[K' + E + b'[0m' + E + b'[3;1Hxyz' + E + b'[3;2H'
             + E + b'[1K' + E + b'[12;40H',
    # Eighty characters leave the cursor on the last column with the wrap pending.
    'pending-wrap': HEAD + b'y' * 80,
    # Modes and cursor state: region, origin, hidden cursor, mouse, paste, focus.
    'modes': HEAD + E + b'[5;10r' + E + b'[?6h' + E + b'[?25l' + E + b'[?1002h' + E + b'[?1006h'
             + E + b'[?2004h' + E + b'[?1004h' + E + b'[?1h' + E + b'=' + E + b'[4h' + E + b'[6 q'
             + E + b'[2;3Hq',
    # The alternate screen: the normal screen's text is not on it.
    'alternate': HEAD + b'normal' + E + b'[?1049h' + E + b'[3;3Halt',
    # Scrolling inside a region: index at the bottom, reverse index at the top,
    # insert line, delete line.
    'scroll': HEAD + b''.join(b'%d\r\n' % n for n in range(1, 10)) + E + b'[3;7r' + E + b'[7;1H\n'
              + b'new' + E + b'[3;1H' + E + b'M' + b'top' + E + b'[5;1H' + E + b'[L' + E + b'[6;1H'
              + E + b'[M',
    # Insert, delete and erase characters; tab stops set and cleared.
    'edit': HEAD + b'abcdefgh' + E + b'[1;3H' + E + b'[2@' + E + b'[1;8H' + E + b'[P'
            + E + b'[2;1H12345678' + E + b'[2;2H' + E + b'[3X' + E + b'[3;5H' + E + b'H' + E + b'[3;9H'
            + E + b'[g' + E + b'[3;1H\tT\tU',
}


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, data in CASES.items():
        (out / (name + '.in')).write_bytes(data)
    print('wrote %d cases' % len(CASES))


if __name__ == '__main__':
    main()
