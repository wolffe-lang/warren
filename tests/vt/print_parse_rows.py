#!/usr/bin/env python3
"""The reference's print screen, read cell by cell: which renditions it wrote outright.

Print screen writes an SGR before each cell whose rendition is not the default,
and the second half of a wide character counts as a cell of its own: it gets an
SGR too, with no character after it. A cell with no rendition that follows a
cell with one gets no reset when the colours are the same. So the first SGR
after a wide character with a rendition belongs to its second half, and the
next cell's own rendition was written outright only if a second SGR follows.
Taking the second half's SGR for the next cell's own made pass A disagree with
pass S on cells that have no rendition (the five seeds of warren#27).
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle  # noqa: E402

E = b'\x1b'


def checksum(cp):
    return '%04X' % ((-cp) & 0xFFFF)


def laid_out(line, cells):
    """One printed row and the code points of its cells (0 for a second half), laid out on 80 columns."""
    sums = [checksum(cp) if cp else '0000' for cp in cells] + ['FFE0'] * (80 - len(cells))
    return oracle.lay_out(oracle.parse_print(line + b'\r\n', 1)[0], sums, 80)


def main():
    failed = []

    def row(name, check):
        try:
            ok, detail = check()
        except Exception as error:
            ok, detail = False, '%s: %s' % (type(error).__name__, error)
        print('%s print-parse %s%s' % ('PASS' if ok else 'FAIL', name, '' if ok else ': %r' % str(detail)[:400]),
              flush=True)
        if not ok:
            failed.append(name)

    def stated(cells):
        return [bool(cell[3]) for cell in cells if cell[0] != 0]

    def second_half_sgr():
        # Italic and invisible `中`, then `한` with no rendition and no reset.
        cells = laid_out(E + b'[0;8;3m\xe4\xb8\xad' + E + b'[0;8;3m\xed\x95\x9cx', [0x4E2D, 0, 0xD55C, 0, ord('x')])
        return stated(cells) == [True, False, False], cells

    def own_sgr_after_second_half():
        # A coloured `文` twice: the second has its own SGR after the first's second half.
        cells = laid_out(E + b'[0;105m\xe6\x96\x87' + E + b'[0;105m' + E + b'[0;105m\xe6\x96\x87' + E + b'[0;105m',
                         [0x6587, 0, 0x6587, 0])
        return stated(cells) == [True, True], cells

    def plain_wide():
        # Two `한` with no rendition: no SGR at all, nothing stated.
        cells = laid_out(b'\xed\x95\x9c\xed\x95\x9c', [0xD55C, 0, 0xD55C, 0])
        return stated(cells) == [False, False], cells

    def narrow_unchanged():
        # Narrow cells keep the rule they had: an SGR just before a cell states it.
        cells = laid_out(E + b'[0;3mab' + E + b'[0mc', [ord('a'), ord('b'), ord('c')])
        return stated(cells) == [True, False, True], cells

    row('second-half-sgr-is-not-the-next-cells', second_half_sgr)
    row('own-sgr-after-a-second-half', own_sgr_after_second_half)
    row('plain-wide-states-nothing', plain_wide)
    row('narrow-cells-unchanged', narrow_unchanged)
    if failed:
        print('FAIL print-parse rows: %s' % ' '.join(failed))
        return 1
    print('PASS print-parse second-half-sgr own-sgr plain-wide narrow')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
