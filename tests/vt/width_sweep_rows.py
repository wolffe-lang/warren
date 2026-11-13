#!/usr/bin/env python3
"""Prove CPR sweep framing and strict reply accounting without an emulator."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / 'tools/vt/width_sweep.py'))


def main():
    commands, positions = MODULE['commands'], MODULE['positions']
    prefix = b'\x1b[1;1H\x1b[2Ka'
    assert commands([0x41, 0x301, 0x4E2D]) == b''.join(
        prefix + chr(cp).encode() + b'\x1b[6n' for cp in (0x41, 0x301, 0x4E2D))
    assert positions(b'\x1b[1;3R\x1b[1;2R\x1b[1;4R', 3) == [(1, 3), (1, 2), (1, 4)]
    for data, count in [(b'\x1b[1;3R', 2), (b'\x1b[1;3R\x1b[1;4R', 1),
                        (b'x\x1b[1;3R', 1), (b'\x1b[1;3Rz', 1), (b'\x1b[0;3R', 1)]:
        try:
            positions(data, count)
        except ValueError:
            pass
        else:
            raise AssertionError('bad CPR accounting accepted: %r' % data)
    print('PASS width-sweep framing combining-base exact-replies malformed-refusal')


if __name__ == '__main__':
    main()
