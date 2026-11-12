#!/usr/bin/env python3
"""The behaviour census: small streams whose outcome a contract must not guess.

Each stream isolates one question (what clears a pending wrap, what an erased
cell keeps, what a malformed sequence does). Their screens are recorded from
the reference emulator into tests/vt/census/ and are the measured answers the
emulator's contract cites. Unlike tests/vt/cases.py, no expectation here was
written by hand first.
"""
from pathlib import Path
import sys

E = b'\x1b'
C = E + b'['
HEAD = E + b']2;t\x07' + C + b'2 q'
FULL = b'y' * 80          # leaves the cursor on column 80 with the wrap pending

CASES = {}


def case(name, data, size=None):
    CASES[name] = (HEAD + data, size)


# 1. What clears a pending wrap. Each stream ends with 'Z': on row 2 column 1
# if the wrap was still pending, somewhere on row 1 if it was cleared.
for name, op in {
    'cr': b'\r', 'bs': b'\b', 'ht': b'\t', 'cuu': C + b'A', 'cud': C + b'B', 'cuf': C + b'C',
    'cub': C + b'D', 'cup-same': C + b'1;80H', 'cha-same': C + b'80G', 'el': C + b'K',
    'el1': C + b'1K', 'ed': C + b'J', 'ech': C + b'X', 'ich': C + b'@', 'dch': C + b'P',
    'il': C + b'L', 'dl': C + b'M', 'sgr': C + b'1m', 'decsc': E + b'7',
    'decsc-decrc': E + b'7' + E + b'8', 'decstbm': C + b'1;24r', 'decawm-off-on': C + b'?7l' + C + b'?7h',
    'dectcem': C + b'?25l', 'decom': C + b'?6h', 'title': E + b']2;u\x07', 'decscusr': C + b'4 q',
    'ri': E + b'M', 'ind': E + b'D', 'hts': E + b'H', 'irm': C + b'4h', 'lf': b'\n', 'da1': C + b'c',
    'nothing': b'',
}.items():
    case('wrap-%s' % name, FULL + op + b'Z')

# 2. Erase and the current rendition.
case('bce-el', C + b'1;4;7;9;31;42m' + C + b'K' + C + b'0m')
case('bce-ed', C + b'3;5;44m' + C + b'2J' + C + b'0m')
case('bce-ech', b'abcdef' + C + b'1;1H' + C + b'1;45m' + C + b'3X' + C + b'0m')
case('bce-ich-dch', b'abcdef' + C + b'1;2H' + C + b'46m' + C + b'2@' + C + b'2;1Habcdef' + C + b'2;2H' + C + b'2P' + C + b'0m')
case('bce-il-scroll', C + b'41m' + C + b'L' + C + b'24;1H\n' + C + b'0m')
case('ed3', b'a\r\n' * 30 + C + b'3J')
case('ed2-cursor', C + b'5;5H' + C + b'2Jx')

# 3. Wide and combining characters at the edges.
W = b'\xe4\xb8\xad'
case('wide-last-column-nowrap', C + b'?7l' + b'y' * 79 + W + b'Z')
case('wide-last-column-wrap', b'y' * 79 + W)
case('wide-overwrite-lead', W + C + b'1;1Hx')
case('wide-overwrite-tail', W + C + b'1;2Hx')
case('wide-erase-tail', W + W + C + b'1;2H' + C + b'1X')
case('wide-dch-tail', W + b'ab' + C + b'1;2H' + C + b'P')
case('wide-ich-split', W + b'ab' + C + b'1;2H' + C + b'@')
case('wide-insert-mode', b'ab' + C + b'1;1H' + C + b'4h' + W)
case('combining-first-cell', b'\xcc\x81a')
case('combining-after-wide', W + b'\xcc\x81')
case('combining-many', b'e' + b'\xcc\x81' * 6)
case('combining-after-wrap', FULL + b'\xcc\x81')
case('zero-width-joiner', b'a\xe2\x80\x8db')
case('emoji', b'\xf0\x9f\x98\x80x')
case('emoji-vs16', b'\xe2\x9d\xa4\xef\xb8\x8fx')

# 4. Cursor motion at the borders.
case('tab-to-end', C + b'1;78H\t\tZ')
case('bs-first-column', b'\b\bZ')
case('cup-clamp', C + b'99;999HZ')
case('cup-zero', C + b'5;5H' + C + b'0;0HZ')
case('cuu-stops-at-region', C + b'5;10r' + C + b'7;1H' + C + b'9AZ')
case('cuu-outside-region', C + b'5;10r' + C + b'3;1H' + C + b'9AZ')
case('cud-outside-region', C + b'5;10r' + C + b'12;1H' + C + b'99BZ')
case('lf-below-region', C + b'5;10r' + C + b'24;1Ha\nZ')
case('lf-bottom-of-screen', C + b'24;1Ha\nZ')
case('ri-top-of-screen', b'a' + E + b'MZ')
case('nel', b'ab' + E + b'EZ')
case('cnl-cpl', C + b'5;5H' + C + b'2EZ' + C + b'3Fz')
case('hpr-vpr', C + b'5a' + C + b'2eZ')
case('cht-cbt', C + b'2IZ' + C + b'ZY')
case('rep', b'a' + C + b'5b')
case('su-sd', b'1\r\n2\r\n3' + C + b'S' + C + b'10;1H' + b'x' + C + b'2T')
case('decaln', E + b'#8')
case('lnm', C + b'20h' + b'a\nb')
case('insert-mode', b'abc' + C + b'1;1H' + C + b'4h' + b'XY')

# 5. Regions, origin, saved cursor, the alternate screen.
case('decstbm-homes', C + b'5;5H' + C + b'3;9rZ')
case('decstbm-one-row', C + b'5;5H' + C + b'5;5rZ')
case('decstbm-inverted', C + b'5;5H' + C + b'10;5rZ')
case('decstbm-past-bottom', C + b'5;5H' + C + b'3;99rZ')
case('decstbm-origin-homes', C + b'?6h' + C + b'3;9rZ')
case('origin-clamps', C + b'3;9r' + C + b'?6h' + C + b'99;5HZ')
case('il-outside-region', b'1\r\n2\r\n3\r\n4' + C + b'3;4r' + C + b'1;1H' + C + b'L')
case('decsc-rendition', C + b'1;31m' + C + b'5;5H' + E + b'7' + C + b'0m' + C + b'1;1H' + E + b'8Z')
case('decrc-never-saved', C + b'5;5H' + C + b'1m' + E + b'8Z')
case('decsc-origin', C + b'3;9r' + C + b'?6h' + C + b'2;2H' + E + b'7' + C + b'?6l' + E + b'8Z')
case('alt-1049-restores-cursor', b'ab' + C + b'?1049h' + C + b'5;5Hx' + C + b'?1049lZ')
case('alt-1049-twice', b'ab' + C + b'?1049h' + b'x' + C + b'?1049h' + b'y')
case('alt-47-keeps', C + b'?47h' + b'alt' + C + b'?47l' + C + b'?47h')
case('alt-rendition-carries', C + b'1;31m' + C + b'?1049h' + b'x')
case('alt-region-shared', C + b'3;9r' + C + b'?1049h' + C + b'1;1HZ')
case('ris', b'ab' + C + b'1;31m' + C + b'3;9r' + C + b'?6h' + C + b'?25l' + C + b'?2004h' + E + b'cZ')
case('decstr', b'ab' + C + b'1;31m' + C + b'3;9r' + C + b'?6h' + C + b'?25l' + C + b'4h' + C + b'!pZ')

# 6. Malformed and unknown input.
case('utf8-truncated-2', b'a\xc3(b')
case('utf8-truncated-3', b'a\xe4\xb8(b')
case('utf8-overlong', b'a\xc0\xafb')
case('utf8-surrogate', b'a\xed\xa0\x80b')
case('utf8-beyond', b'a\xf4\x90\x80\x80b')
case('utf8-lone-continuation', b'a\x80b')
case('utf8-ff', b'a\xffb')
case('utf8-real-replacement', b'a\xef\xbf\xbdb')
case('utf8-low-sixteen-zero', b'a\xf0\x90\x80\x80b')
case('c1-as-utf8-csi', b'\xc2\x9b31mX')
case('c1-raw-csi', b'\x9b31mX')
case('c0-inside-csi', C + b'3\r1mX')
case('lf-inside-csi', b'ab' + C + b'1\n;31mX')
case('can-inside-csi', C + b'31\x18mX')
case('sub-inside-csi', C + b'31\x1amX')
case('esc-inside-csi', C + b'31' + C + b'1mX')
case('csi-many-params', C + b';'.join([b'1'] * 40) + b';4mX')
case('csi-huge-param', C + b'99999999999999999999CX')
case('csi-unknown-final', C + b'5yX')
case('csi-private-unknown', C + b'?9999hX')
case('csi-intermediate-unknown', C + b'5 zX')
case('csi-gt', C + b'>4;2mX')
case('esc-unknown', E + b'jX')
case('osc-bel', E + b']2;abc\x07X')
case('osc-st', E + b']2;abc' + E + b'\\X')
case('osc-unterminated-lf', E + b']2;abc\nX')
case('osc-unknown', E + b']777;hello\x07X')
case('osc-icon-only', E + b']1;icon\x07X')
case('osc-0', E + b']0;both\x07X')
case('osc-utf8', E + b']2;\xe4\xb8\xad\x07X')
case('dcs', E + b'Pqqq' + E + b'\\X')
case('apc', E + b'_app' + E + b'\\X')
case('pm', E + b'^pm' + E + b'\\X')
case('sos', E + b'Xsos' + E + b'\\X')
case('dcs-unterminated-bel', E + b'Pqqq\x07X' + E + b'\\Y')

# 7. SGR forms.
case('sgr-colon-256', C + b'38:5:196mX')
case('sgr-colon-rgb-empty-space', C + b'38:2::1:2:3mX')
case('sgr-colon-rgb-no-space', C + b'38:2:1:2:3mX')
case('sgr-truncated-256', C + b'38;5mX')
case('sgr-truncated-rgb', C + b'38;2;1;2mX')
case('sgr-256-out-of-range', C + b'38;5;999mX')
case('sgr-rgb-out-of-range', C + b'38;2;999;0;0mX')
case('sgr-underline-colon', C + b'4:3mX')
case('sgr-underline-colour', C + b'58;2;1;2;3mX')
case('sgr-underline-colour-colon', C + b'58:2::1:2:3mX')
case('sgr-double-underline', C + b'21mX')
case('sgr-overline', C + b'53mX')
case('sgr-resets', C + b'1;2;3;4;5;7;8;9m' + C + b'22;23;24;25;27;28;29mX')
case('sgr-22-clears-both', C + b'1;2m' + C + b'22mX')
case('sgr-bright-bg', C + b'100;97mX')
case('sgr-empty-is-reset', C + b'1;31m' + C + b'mX')
case('sgr-mixed-after-38', C + b'38;5;1;1;48;5;2mX')

# 8. Character sets.
case('charset-dec-graphics', E + b'(0lqk' + E + b'(Bq')
case('charset-so-si', E + b')0' + b'q\x0eq\x0fq')

# 9. Resize: the stream is replayed, then the screen is resized by the harness.
case('resize-narrower', b'y' * 100 + b'\r\nab', size=[(60, 24)])
case('resize-wider', b'y' * 100 + b'\r\nab', size=[(100, 24)])
case('resize-shorter', b''.join(b'%d\r\n' % n for n in range(1, 24)) + b'end', size=[(80, 10)])
case('resize-taller', b''.join(b'%d\r\n' % n for n in range(1, 40)) + b'end', size=[(80, 30)])
case('resize-region-tabs', C + b'3;9r' + C + b'3g' + C + b'1;5H' + E + b'H', size=[(100, 30)])
case('resize-alt', C + b'?1049h' + b'y' * 100, size=[(60, 10)])
# Not recorded: a wide character cut in half by a narrower screen. The reference
# emulator keeps an orphan first half there, which no copy or print can show whole.


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for name, (data, size) in CASES.items():
        if size:
            body = b'warren-rec 1\nsize 80 24\no %d\n' % len(data) + data + b'\n'
            body += b''.join(b'r %d %d\n' % s for s in size)
            (out / (name + '.in')).write_bytes(body)
        else:
            (out / (name + '.in')).write_bytes(data)
    print('wrote %d census cases' % len(CASES))


if __name__ == '__main__':
    main()
