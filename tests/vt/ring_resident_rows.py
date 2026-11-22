#!/usr/bin/env python3
"""warren#67: one pane's resident cost, measured and held.

    ring_resident_rows.py [--measure] [--takes N] [--takes-file FILE] MEASURE_CHILD RING_PROBE

Each stage of ring-probe (src/ring_probe.lu) runs in a process of its own,
spawned by measure-child, the small C parent: `none` once a take, then `new`,
`resize`, `screenful` and `filled` at history caps of 0, 2 MiB and 8 MiB
(`filled` only where there is a ring), every pair TAKES times (3).

Every run prints, raw, measure-child's peak, the floor it reports (the C
child's high-water mark before exec, which ru_maxrss keeps across exec; it
reads 0 in some runs on Linux, and is never used in arithmetic) and the
parent's own peak, the same take's `none` peak, and, where the host has
/proc, the probe's last VmRSS and VmHWM. Nothing is subtracted without being
printed. The quantity a row holds is printed beside its formula:
  new                          increment = peak(new, CAP) - peak(none)
  resize, screenful, filled    increment = peak(STAGE, CAP) - peak(new, CAP)
each within one take, and `ratio = increment / CAP` where CAP > 0. A `new`
increment carries what the first pane in a fresh process pays once (the
emulator's code paged in, the allocator's first chunk) as well as the pane.

The bound of a row is read from the takes recorded for this host in
tests/vt/ring-resident-takes.json: the largest recorded increment, plus a
margin that is the largest of three times the recorded spread, 5% of the
largest recorded peak of that stage, or one allocation granule (256 KiB on
Linux, 16 KiB on macOS). The rule checks itself where a ring is made: a `new`
row's margin must be under one cap, so one more cap-sized buffer at the peak
fails; a difference row's margin must be under two caps, so a step that made
the ring again fails. A margin past that fails by name as too loose. A host
with no recorded takes fails by name. A cap a host does not hold (macOS at
8 MiB, whose allocator's peak there is bimodal) is measured, printed and named
in a NOTE with its takes, and holds nothing. Each verdict names its row: `ring-resident-STAGE`
(new, resize, screenful, filled), `ring-resident-projection`, `ring-resident-takes`
and `ring-resident-probe`.

The projection row holds the server's projection of an 80x24 pane
(`pane_bytes`, printed by the probe) at or above the largest `new` increment
at the server's history cap, and prints how far above.

Every run ends its measurements with one `TAKES-JSON` line for this host, in
the form the takes file records; --measure stops there and holds nothing.
Exit 0 when every row holds, 1 when one does not, 2 on a probe that did not
run.
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CAPS = (0, 2097152, 8388608)
STAGES = ('new', 'resize', 'screenful', 'filled')
GRANULE = {'linux': 262144, 'macos': 16384}
# The caps each host holds. macOS's peaks are whole 16 KiB pages and the same
# to the byte from run to run at 0 and 2 MiB (the server's cap), but at 8 MiB
# one run in four peaks a whole cap higher (its allocator keeping the first
# freed buffer at the peak), so there it is measured and printed, not held.
HELD_CAPS = {'linux': (0, 2097152, 8388608), 'macos': (0, 2097152)}
TAKES_FILE = Path(__file__).with_name('ring-resident-takes.json')
MEASURE = re.compile(r'^MEASURE process exit=(\d+) signal=(\d+) wall-nanoseconds=(\d+) peak-rss-bytes=(\d+) '
                     r'child-before-exec-peak-rss-bytes=(-?\d+) parent-inherited-peak-rss-bytes=(-?\d+) ')
STEP = re.compile(r'^RING-PROBE stage=\S+ cap=\d+ step=(\S+) vmrss-kb=(-?\d+) vmhwm-kb=(-?\d+) '
                  r'history-used=(\d+) history-evicted=(\d+)$')
PROJECTION = re.compile(r'^RING-PROBE-PROJECTION history-bytes=(\d+) pane-bytes-80x24=(\d+)$')


def this_host():
    return 'macos' if sys.platform == 'darwin' else 'linux'


def pairs():
    for cap in CAPS:
        for stage in STAGES:
            if stage == 'filled' and cap == 0:
                continue
            yield stage, cap


def key(stage, cap):
    return '%s %d' % (stage, cap)


def run(measure_child, probe, stage, cap):
    done = subprocess.run([measure_child, probe, stage, str(cap)], capture_output=True, text=True,
                          errors='replace', timeout=900)
    got = {'exit': None, 'step': '-', 'vmrss': -1, 'vmhwm': -1, 'projection': None}
    for line in done.stdout.splitlines():
        m = MEASURE.match(line)
        if m:
            got.update(exit=int(m.group(1)), signal=int(m.group(2)), nanos=int(m.group(3)), peak=int(m.group(4)),
                       floor=int(m.group(5)), parent=int(m.group(6)))
        m = STEP.match(line)
        if m:
            got.update(step=m.group(1), vmrss=int(m.group(2)), vmhwm=int(m.group(3)), used=int(m.group(4)),
                       evicted=int(m.group(5)))
        m = PROJECTION.match(line)
        if m:
            got['projection'] = (int(m.group(1)), int(m.group(2)))
    last = 'start' if stage == 'none' else stage
    if got['exit'] != 0 or got['step'] != last:
        print('FAIL ring-resident-probe %s cap=%d: exit %s at step %s' % (stage, cap, got['exit'], got['step']))
        sys.stdout.write(done.stdout[-2000:])
        sys.stderr.write(done.stderr[-2000:])
        return None
    return got


def bound(increments, peaks, granule):
    """The bound, its margin, and the parts the margin was the largest of."""
    top = max(increments)
    spread = top - min(increments)
    margin = max(3 * spread, max(peaks) // 20, granule)
    return top + margin, margin


def too_loose(stage, cap, margin):
    """Why a margin cannot see what its row is for, or None."""
    if cap == 0:
        return None
    if stage == 'new' and margin >= cap:
        return 'margin %d is not under one cap (%d): one more cap-sized buffer at the peak would pass' % (margin, cap)
    if stage != 'new' and margin >= 2 * cap:
        return 'margin %d is not under two caps (%d): a step that made the ring again would pass' % (margin, 2 * cap)
    return None


def self_test():
    cap = 2097152
    granule = 262144
    # Close takes of a pane at about 3.7 caps: the takes pass, one more cap fails.
    inc = [7471104, 7720960, 7872512]
    peaks = [10055680, 10268672, 10347520]
    held, margin = bound(inc, peaks, granule)
    assert max(inc) <= held < max(inc) + cap and too_loose('new', cap, margin) is None, (held, margin)
    # A spread that wide cannot hold a `new` row: the rule says so by name.
    _, margin = bound([7000000, 7800000, 8600000], peaks, granule)
    assert too_loose('new', cap, margin) is not None, margin
    # A difference row: noise of half a megabyte passes, the ring made again (two caps) fails.
    held, margin = bound([-544768, 147456, 229376], [9723904, 10285056, 10244096], granule)
    assert 229376 <= held < 2 * cap and too_loose('resize', cap, margin) is None, (held, margin)
    print('PASS ring-resident-self-test')


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--measure', action='store_true')
    p.add_argument('--takes', type=int, default=3)
    p.add_argument('--takes-file', type=Path, default=TAKES_FILE)
    p.add_argument('measure_child')
    p.add_argument('probe')
    args = p.parse_args()
    self_test()
    host = this_host()
    granule = GRANULE[host]
    held = {}
    projection = None
    for take in range(1, args.takes + 1):
        none = run(args.measure_child, args.probe, 'none', 0)
        if none is None:
            return 2
        projection = none['projection']
        print('MEASURE ring-resident host=%s stage=none cap=0 take=%d peak=%d floor=%d parent=%d vmrss-kb=%d vmhwm-kb=%d'
              % (host, take, none['peak'], none['floor'], none['parent'], none['vmrss'], none['vmhwm']))
        new = {}
        for stage, cap in pairs():
            got = run(args.measure_child, args.probe, stage, cap)
            if got is None:
                return 2
            if stage == 'new':
                new[cap] = got['peak']
                base, formula = none['peak'], 'peak(new) - peak(none)'
            else:
                base, formula = new[cap], 'peak(%s) - peak(new)' % stage
            increment = got['peak'] - base
            ratio = '%.3f' % (increment / cap) if cap else '-'
            print('MEASURE ring-resident host=%s stage=%s cap=%d take=%d peak=%d floor=%d parent=%d none=%d '
                  'increment=%d ratio=%s vmrss-kb=%d vmhwm-kb=%d formula="%s"'
                  % (host, stage, cap, take, got['peak'], got['floor'], got['parent'], none['peak'], increment, ratio,
                     got['vmrss'], got['vmhwm'], formula))
            row = held.setdefault(key(stage, cap), {'increments': [], 'peaks': []})
            row['increments'].append(increment)
            row['peaks'].append(got['peak'])
    print('TAKES-JSON ' + json.dumps({host: {'pairs': held}}, sort_keys=True))
    if args.measure:
        return 0
    recorded = json.loads(args.takes_file.read_text()) if args.takes_file.exists() else {}
    if host not in recorded:
        print('FAIL ring-resident-takes host=%s: no recorded takes in %s' % (host, args.takes_file.name))
        print('RING-RESIDENT rows=1 failed=1')
        return 1
    print('ring-resident: %s takes recorded from %s' % (host, recorded[host].get('source', 'an unnamed source')))
    failed = 0
    rows = 0
    for stage, cap in pairs():
        name = key(stage, cap)
        if cap not in HELD_CAPS[host]:
            print('NOTE ring-resident-%s cap=%d host=%s: measured, not held; increments %s'
                  % (stage, cap, host, held[name]['increments']))
            continue
        rows += 1
        takes = recorded[host]['pairs'].get(name)
        if not takes:
            print('FAIL ring-resident-%s cap=%d: no recorded takes for host=%s' % (stage, cap, host))
            failed += 1
            continue
        limit, margin = bound(takes['increments'], takes['peaks'], granule)
        loose = too_loose(stage, cap, margin)
        worst = max(held[name]['increments'])
        ratio = ' (ratio %.2fx, bound %.2fx)' % (worst / cap, limit / cap) if cap else ''
        if loose:
            print('FAIL ring-resident-%s cap=%d: bound too loose: %s' % (stage, cap, loose))
            failed += 1
        elif worst > limit:
            print('FAIL ring-resident-%s cap=%d increment=%d past bound=%d%s; recorded %s, margin %d'
                  % (stage, cap, worst, limit, ratio, takes['increments'], margin))
            failed += 1
        else:
            print('PASS ring-resident-%s cap=%d increment=%d bound=%d%s; margin %d'
                  % (stage, cap, worst, limit, ratio, margin))
    rows += 1
    if projection is None:
        print('FAIL ring-resident-projection: the probe printed none')
        failed += 1
    else:
        history_bytes, pane_bytes = projection
        name = key('new', history_bytes)
        if name not in held:
            print('FAIL ring-resident-projection: no `new` row at the server\'s cap %d' % history_bytes)
            failed += 1
        else:
            measured = max(held[name]['increments'])
            if pane_bytes < measured:
                print('FAIL ring-resident-projection pane-bytes-80x24=%d under the measured %d' % (pane_bytes, measured))
                failed += 1
            else:
                print('PASS ring-resident-projection pane-bytes-80x24=%d measured=%d over=%.2fx'
                      % (pane_bytes, measured, pane_bytes / measured))
    print('RING-RESIDENT rows=%d failed=%d' % (rows, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
