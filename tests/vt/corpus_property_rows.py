#!/usr/bin/env python3
"""Crosscheck the property helper's framing, exact bytes and actual CLI replay."""
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
from corpus_properties import encode, observe


def main():
    program, warren = sys.argv[1:]
    for stream in (
        [('size', (4, 2)), ('o', b'A\0\xff')],
        [('size', (4, 2)), ('o', b'a'), ('i', b'ignored\n\xff'), ('r', (6, 3)), ('o', '中'.encode())],
    ):
        protocol, counts = encode(stream)
        got, frame = observe(program, protocol, counts)
        assert got.returncode == 0 and not got.stderr, (got.returncode, got.stderr, got.stdout[-1000:])
        record = bytearray(b'warren-rec 1\nsize %d %d\n' % stream[0][1])
        for kind, value in stream[1:]:
            if kind == 'r':
                record += b'r %d %d\n' % value
            else:
                record += b'%s %d\n' % (kind.encode(), len(value)) + value + b'\n'
        baseline = subprocess.run([warren, 'vt-dump', '--history-bytes', '1048576', '--replay'],
                                  cwd=ROOT, input=record, capture_output=True, timeout=30)
        assert baseline.returncode == 0 and baseline.stdout == frame, (baseline.stderr, frame)
    header = b'WRP1' + struct.pack('<II', 4, 2)
    for data in (b'', b'bad-magic', header, header + b'\x03\0',
                 header + b'\x01' + struct.pack('<I', 100) + b'X\0', header + b'\0extra'):
        result = subprocess.run([program], cwd=ROOT, input=data, capture_output=True, timeout=30)
        assert result.returncode == 2, (data, result.returncode, result.stderr)
    print('PASS corpus-property-framing binary-byte-count rolling resize ignored-input CLI-identity malformed-refusal')


if __name__ == '__main__':
    main()
