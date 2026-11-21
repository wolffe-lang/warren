#!/usr/bin/env python3
"""Run a row program under measure-child and hold its peak to a stated bound.

    peak_bound.py --name NAME --bound BYTES -- MEASURE_CHILD PROGRAM [ARG ...]

The program's own output passes through. measure-child's MEASURE line gives
the program's peak resident size; the wrapper prints

    PEAK NAME peak-rss-bytes=N bound=B

and then one verdict: `PASS peak-bound NAME ...` when the program exited 0
within its bound; `FAIL peak-bound NAME peak-rss-bytes=N bound=B` (exit 1) when
it went past it; `FAIL peak-bound NAME exit=E ...` with the program's own
status when it failed; `FAIL peak-bound NAME killed signal=S ...` with 128+S
when a signal ended it, so a program the kernel kills for memory is named
with its peak. No MEASURE line is exit 2.
"""
import argparse
import re
import subprocess
import sys

MEASURE = re.compile(r'^MEASURE process exit=(\d+) signal=(\d+) wall-nanoseconds=\d+ peak-rss-bytes=(\d+) ')


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--name', required=True)
    p.add_argument('--bound', required=True, type=int)
    p.add_argument('command', nargs=argparse.REMAINDER)
    args = p.parse_args()
    command = args.command[1:] if args.command[:1] == ['--'] else args.command
    if args.bound <= 0 or not command:
        print('FAIL peak-bound %s: a positive --bound and a command are required' % args.name, flush=True)
        return 2
    child = subprocess.Popen(command, stdout=subprocess.PIPE, text=True, errors='replace')
    measured = None
    for line in child.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        m = MEASURE.match(line)
        if m:
            measured = (int(m.group(1)), int(m.group(2)), int(m.group(3)))
    code = child.wait()
    if measured is None:
        print('FAIL peak-bound %s: no MEASURE line (exit %d)' % (args.name, code), flush=True)
        return code if code > 2 else 2
    status, signal, peak = measured
    print('PEAK %s peak-rss-bytes=%d bound=%d' % (args.name, peak, args.bound))
    if signal:
        print('FAIL peak-bound %s killed signal=%d peak-rss-bytes=%d bound=%d' % (args.name, signal, peak, args.bound))
        return 128 + signal
    if status:
        print('FAIL peak-bound %s exit=%d peak-rss-bytes=%d bound=%d' % (args.name, status, peak, args.bound))
        return status
    if peak > args.bound:
        print('FAIL peak-bound %s peak-rss-bytes=%d bound=%d' % (args.name, peak, args.bound))
        return 1
    print('PASS peak-bound %s peak-rss-bytes=%d bound=%d (%.2f of it)' % (args.name, peak, args.bound,
                                                                     peak / args.bound))
    return 0


if __name__ == '__main__':
    sys.exit(main())
