#!/usr/bin/env python3
"""The fresh drive's source trace follows the reference's wide scalar at the last
column with autowrap off (warren#28): it clears a pending wrap, replaces the wide
glyph just written in the same run, and is dropped after anything else. The
trace only checks the reference's cursor, so the rows hold the cursor after
autowrap is turned on again, where the pending wrap decides the next print.
Each expected cursor is the reference's (tests/vt/wide_pending_rows.py)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from erase_extent_fixture import trace  # noqa: E402

OFF = b'\x1b[?7l'
ON = b'\x1b[?7h'
ROWS = (
    # (name, stream, the reference's cursor row and column after it)
    ('narrow-pending-wide-then-print', OFF + b'\x1b[1;8Hx' + '中'.encode() + ON + b'A', [1, 8]),
    ('narrow-pending-wide-then-wide', OFF + b'\x1b[1;8Hx' + '中'.encode() + ON + 'あ'.encode(), [2, 3]),
    ('wide-in-run-replaces-then-print', OFF + b'\x1b[1;7H' + '文あ'.encode() + ON + b'A', [1, 8]),
    ('wide-in-run-clears-wrap', OFF + b'\x1b[1;7H' + '文あ'.encode() + ON + b'AB', [2, 2]),
    ('wide-across-sgr-is-dropped', OFF + b'\x1b[1;7H' + '文'.encode() + b'\x1b[m' + 'あ'.encode() + ON + b'A', [1, 8]),
    ('wide-across-del-is-dropped', OFF + b'\x1b[1;7H' + '文'.encode() + b'\x7f' + 'あ'.encode() + ON + b'A', [1, 8]),
    ('wide-before-last-column-replaced', OFF + b'\x1b[1;6H' + '中あ'.encode(), [1, 8]),
    ('wide-after-narrow-in-run-is-dropped', OFF + b'\x1b[1;7H' + '文x中'.encode() + ON + b'A', [1, 8]),
)


def main():
    failed = 0
    for name, stream, want in ROWS:
        got = trace(stream, 8, 3)['cursor']
        if got == want:
            print('PASS wide-pending-source-trace %s cursor=%d;%d' % (name, got[0], got[1]))
        else:
            print('FAIL wide-pending-source-trace %s cursor expected %d;%d got %d;%d' % (name, want[0], want[1], got[0], got[1]))
            failed += 1
    print('WIDE-PENDING-TRACE rows=%d failed=%d' % (len(ROWS), failed))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
