#!/usr/bin/env python3
"""Prove corpus rechunking preserves output, input and resize boundaries."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / 'tests/vt/chunking_suite.py'))


def collapse(stream):
    result = []
    for kind, value in stream:
        if kind == 'o' and result and result[-1][0] == 'o':
            result[-1] = ('o', result[-1][1] + value)
        else:
            result.append((kind, value))
    return result


def main():
    events, encode = MODULE['events'], MODULE['encode']
    stream = [('size', (8, 3)), ('o', b'\x1b[31mA\xe4\xb8\xad' * 100),
              ('i', b'ignored\n\x1b[2J'), ('r', (4, 5)), ('o', b'\x1b[0mZ')]
    for strategy in ('bytewise', 'random'):
        data = encode(stream, strategy)
        got = events(data, True)
        assert collapse(got) == stream
        assert data == encode(stream, strategy)
        assert all(0 < len(value) <= (1 if strategy == 'bytewise' else 257)
                   for kind, value in got if kind == 'o')
    raw = b'warren-rec 1\n\x00\xff'
    assert events(raw, False) == [('size', (80, 24)), ('o', raw)]
    assert events(encode([('size', (1, 1)), ('o', b'')], 'bytewise'), True)[1] == ('o', b'')
    print('PASS corpus rechunking bytewise seeded-random binary-input resize empty-output')


if __name__ == '__main__':
    main()
