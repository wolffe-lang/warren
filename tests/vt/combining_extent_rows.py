#!/usr/bin/env python3
"""G6/R1: adding a combining mark to an unwritten blank creates content."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen


def main():
    assert len(sys.argv) > 1
    command = sys.argv[1:]
    body = b'\x1b[1;5H' + '́'.encode()
    original = command + ['vt-dump', '--cols', '12', '--rows', '2', '--history-bytes', '4096']
    failed = 0
    for label, prefix in (('primary', b''), ('alternate', b'\x1b[?47h')):
        got = subprocess.run(original, input=prefix + body, capture_output=True, cwd=ROOT, timeout=30)
        assert got.returncode == 0 and not got.stderr
        frame = screen.loads(got.stdout.decode())
        assert frame['rows'][0][3][1] == 'U+0020+U+0301', 'fixture must actually store a mark on an unwritten blank'
        good = frame['extents'][0] == 4
        failed += not good
        print('%s combining-unwritten-%s G6 extent=%d expected=4' %
              ('PASS' if good else 'FAIL', label, frame['extents'][0]), flush=True)
    replay = b'warren-rec 1\nsize 12 2\no %d\n' % len(body) + body + b'\nr 6 4\n'
    got = subprocess.run(command + ['vt-dump', '--replay', '--history-bytes', '4096'], input=replay,
                         capture_output=True, cwd=ROOT, timeout=30)
    assert got.returncode == 0 and not got.stderr
    frame = screen.loads(got.stdout.decode())
    count = sum('U+0301' in cell[1] for row in frame['rows'] for cell in row)
    good = count == 1
    failed += not good
    print('%s combining-unwritten-resize R1 marks=%d expected=1' % ('PASS' if good else 'FAIL', count), flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
