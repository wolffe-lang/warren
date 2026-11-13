#!/usr/bin/env python3
"""Hold the small-parent resource wrapper to real child exits and signals."""
import re
import subprocess
import sys


def main():
    tool = sys.argv[1]
    for code in (0, 7):
        got = subprocess.run([tool, sys.executable, '-I', '-c', 'raise SystemExit(%d)' % code], capture_output=True, timeout=20)
        assert got.returncode == code, got
        assert ('exit=%d signal=0 ' % code).encode() in got.stdout, got.stdout
        for field in ('wall-nanoseconds', 'peak-rss-bytes', 'child-before-exec-peak-rss-bytes', 'parent-inherited-peak-rss-bytes'):
            match = re.search((field + r'=(\d+)').encode(), got.stdout)
            assert match, got.stdout
    got = subprocess.run([tool, sys.executable, '-I', '-c', 'import os,signal; os.kill(os.getpid(),signal.SIGTERM)'],
                         capture_output=True, timeout=20)
    assert got.returncode == 143 and b'exit=143 signal=15 ' in got.stdout, got
    got = subprocess.run([tool, '/no/such/resource-observer'], capture_output=True, timeout=20)
    assert got.returncode == 127 and b'exit=127' in got.stdout, got
    print('PASS resource-wrapper child-success child-failure child-signal exec-failure rss-floor-fields')


if __name__ == '__main__':
    main()
