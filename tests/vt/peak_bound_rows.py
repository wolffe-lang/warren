#!/usr/bin/env python3
"""Hold the peak wrapper (tools/vt/peak_bound.py) to what a gate step needs from it.

    peak_bound_rows.py MEASURE_CHILD

The wrapper runs a row program under measure-child and holds its peak resident
size to a bound stated beside the gate step, so a program that grows shows as
a red row naming its peak, not as a kill with no name. Children here are small
Python programs that touch a known number of MiB, one byte a page.
"""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WRAPPER = ROOT / 'tools/vt/peak_bound.py'
MIB = 1 << 20
TOUCH = ('import os, sys\n'
         'n = int(sys.argv[1]) << 20\n'
         'b = bytearray(n)\n'
         'b[::4096] = b"\\x01" * len(range(0, n, 4096))\n'
         'print("child touched", sys.argv[1], flush=True)\n'
         'how = sys.argv[2]\n'
         'if how == "kill":\n'
         '    import signal\n'
         '    os.kill(os.getpid(), signal.SIGKILL)\n'
         'raise SystemExit(int(how))\n')


def run(name, bound, *command):
    return subprocess.run([sys.executable, '-I', str(WRAPPER), '--name', name, '--bound', str(bound), '--',
                           *command], capture_output=True, text=True, timeout=120)


def child(measure, mib, how):
    return [measure, sys.executable, '-I', '-c', TOUCH, str(mib), how]


def peak_of(text, name):
    m = re.search(r'^PEAK %s peak-rss-bytes=(\d+) bound=(\d+)$' % re.escape(name), text, re.M)
    return (int(m.group(1)), int(m.group(2))) if m else None


def main():
    measure = sys.argv[1]
    failed = []

    def row(name, ok, why):
        print(('PASS ' if ok else 'FAIL ') + 'peak-bound-rows ' + name + ('' if ok else ': ' + why))
        if not ok:
            failed.append(name)

    if not WRAPPER.exists():
        print('FAIL peak-bound-rows: no %s' % WRAPPER.relative_to(ROOT))
        return 1

    got = run('under', 512 * MIB, *child(measure, 16, '0'))
    peak = peak_of(got.stdout, 'under')
    row('under', got.returncode == 0 and peak is not None and peak[0] >= 16 * MIB and peak[1] == 512 * MIB
        and 'PASS peak-bound under ' in got.stdout and 'child touched 16' in got.stdout,
        'exit %d, peak %r: %s' % (got.returncode, peak, got.stdout[-400:]))

    got = run('over', 32 * MIB, *child(measure, 96, '0'))
    peak = peak_of(got.stdout, 'over')
    row('over', got.returncode == 1 and peak is not None and peak[0] >= 96 * MIB
        and re.search(r'^FAIL peak-bound over peak-rss-bytes=\d+ bound=%d' % (32 * MIB), got.stdout, re.M) is not None,
        'exit %d, peak %r: %s' % (got.returncode, peak, got.stdout[-400:]))

    got = run('own-exit', 512 * MIB, *child(measure, 8, '7'))
    peak = peak_of(got.stdout, 'own-exit')
    row('child-exit-passes-through', got.returncode == 7 and peak is not None
        and re.search(r'^FAIL peak-bound own-exit exit=7 ', got.stdout, re.M) is not None,
        'exit %d, peak %r: %s' % (got.returncode, peak, got.stdout[-400:]))

    got = run('grows', 512 * MIB, *child(measure, 64, 'kill'))
    peak = peak_of(got.stdout, 'grows')
    row('kill-names-its-peak', got.returncode == 137 and peak is not None and peak[0] >= 64 * MIB
        and re.search(r'^FAIL peak-bound grows killed signal=9 peak-rss-bytes=\d+ bound=', got.stdout, re.M) is not None,
        'exit %d, peak %r: %s' % (got.returncode, peak, got.stdout[-400:]))

    got = run('unmeasured', 512 * MIB, sys.executable, '-I', '-c', 'print("no measure")')
    row('no-measure-line', got.returncode == 2 and 'FAIL peak-bound unmeasured: no MEASURE line' in got.stdout,
        'exit %d: %s' % (got.returncode, got.stdout[-400:]))

    got = subprocess.run([sys.executable, '-I', str(WRAPPER), '--name', 'x', '--bound', '0', '--', 'true'],
                         capture_output=True, text=True, timeout=30)
    row('bound-must-be-positive', got.returncode == 2, 'exit %d' % got.returncode)

    if failed:
        return 1
    print('PASS peak-bound-rows under over child-exit kill no-measure bound-positive')
    return 0


if __name__ == '__main__':
    sys.exit(main())
