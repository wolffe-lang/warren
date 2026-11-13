#!/usr/bin/env python3
"""Observer deadlines preserve binary input, child failure and timeout failure."""
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
observe = runpy.run_path(str(ROOT / 'tests/vt/compare_suite.py'))['observe']


def main():
    command = [sys.executable, '-I', '-c', 'import sys; sys.stdout.buffer.write(sys.stdin.buffer.read()[::-1])']
    data = b'\x00\xffabc' * 2000
    got = observe(command, data, 5, 'binary')
    assert got.returncode == 0 and got.stdout == data[::-1] and not got.stderr
    delayed = [sys.executable, '-I', '-c', 'import sys,time; time.sleep(0.1); sys.stdout.buffer.write(sys.stdin.buffer.read()[::-1])']
    large = data * 20
    got = observe(delayed, large, 5, 'retry-pending-binary-input', interval=0.02)
    assert got.returncode == 0 and got.stdout == large[::-1] and not got.stderr
    got = observe([sys.executable, '-I', '-c', 'raise SystemExit(7)'], b'', 5, 'failure')
    assert got.returncode == 7
    try:
        observe([sys.executable, '-I', '-c', 'import time; time.sleep(1)'], b'', 0.05, 'timeout')
    except subprocess.TimeoutExpired:
        pass
    else:
        raise AssertionError('observer timeout treated as a completed comparison')
    print('PASS observer-deadline binary child-failure timeout-is-error')


if __name__ == '__main__':
    main()
