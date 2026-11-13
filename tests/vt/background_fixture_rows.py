#!/usr/bin/env python3
"""Independent saved-background fixture state; never uses candidate output."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
repair = runpy.run_path(str(ROOT / 'tools/vt/repair_background_fixture.py'))['repair']
E = b'\x1b'
C = E + b'['


def main():
    untouched = b'abc\xe4\xb8\xad' + C + b'48;5;181m' + C + b'7m'
    assert repair(untouched) == (untouched, []), 'D9 must inject nothing without a restore'
    source = E + b'7' + C + b'48;5;181m' + E + b'8'
    fixed, events = repair(source)
    assert fixed == source + C + b'49m', 'restore DEFAULT, not the stale palette colour'
    assert len(events) == 1 and events[0]['original_offset'] == len(source)
    for setter, intervening, correction in (
        (C + b'40m', C + b'48;2;237;31;126m', C + b'48;5;0m'),
        (C + b'48;2;1;2;3m', C + b'48;5;255m', C + b'48;2;1;2;3m'),
        (C + b'38;5;48m', C + b'48;5;181m', C + b'49m'),
        (C + b'38;2;40;49;100m', C + b'48;5;181m', C + b'49m'),
        (C + b'48;5;1m' + C + b'0m', C + b'48;5;181m', C + b'49m'),
    ):
        data = setter + E + b'7' + intervening + E + b'8'
        got, events = repair(data)
        assert got == data + correction, (data, got, correction)
        assert len(events) == 1
    # A repeat 1049 set saves the alternate cache, not the primary one.
    h, l = C + b'?1049h', C + b'?1049l'
    p1, p2, p3 = (C + b'48;5;%dm' % n for n in (1, 2, 3))
    data = p1 + h + p2 + h + p3 + E + b'8' + l + l
    got, events = repair(data)
    assert got == p1 + h + p2 + h + p3 + E + b'8' + p2 + l + p1 + l + p1
    assert [event['background'] for event in events] == [['idx', 2], ['idx', 1], ['idx', 1]]
    for data in (E + b'[31', E + b']2;unfinished', E):
        try:
            repair(data)
        except ValueError:
            pass
        else:
            raise AssertionError('unowned incomplete fixture syntax was guessed')
    print('PASS D9 background-fixture no-injection default palette RGB foreground-skip per-screen-cache malformed-refusal')


if __name__ == '__main__':
    main()
