#!/usr/bin/env python3
"""warren#67: one pane's resident cost, measured and held.

    ring_resident_rows.py [--measure] [--takes N] [--takes-file FILE] MEASURE_CHILD RING_PROBE

Each stage of ring-probe (src/ring_probe.lu) runs in a process of its own,
spawned by measure-child, the small C parent: `none` once, then `new`,
`resize`, `screenful` and `filled` at history caps of 0, 2 MiB and 8 MiB
(`filled` only where there is a ring), every pair TAKES times (3).

Every run prints, raw, measure-child's peak, the floor it reports (the C
child's high-water mark before exec, which ru_maxrss keeps across exec) and
the parent's own peak, the same take's `none` peak, and, where the host has
/proc, the probe's last VmRSS and VmHWM. Nothing is subtracted without being
printed. The quantity a row holds is printed beside its formula:
  new                          increment = peak(new, CAP) - peak(none)
  resize, screenful, filled    increment = peak(STAGE, CAP) - peak(new, CAP)
each within one take, and `ratio = increment / CAP` where CAP > 0.

The bound of a row is read from the takes recorded for this host in
tests/vt/ring-resident-takes.json: the largest recorded take, plus a margin
that is the largest of three times their spread, 5% of the largest, or one
allocation granule (256 KiB on Linux, 16 KiB on macOS). A `new` row whose
bound would come out above 2.6 times its cap is held to 2.6 times instead,
so that no spread lets a second copy of the ring (about 3 times) or a doubled
ring (about 4 times) pass. A host with no recorded takes fails by name.

The projection row holds the server's projection of an 80x24 pane
(`pane_bytes`, printed by the probe) at or above the largest `new` increment
at the server's history cap, and prints how far above.

Every run ends its measurements with one `TAKES-JSON` line for this host, the
form the takes file records; --measure stops there and holds nothing. Exit 0 when every row holds, 1 when one does not,
2 on a probe that did not run.
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
BAND = 2.6
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
        print('FAIL ring-resident probe %s cap=%d: exit %s at step %s' % (stage, cap, got['exit'], got['step']))
        sys.stdout.write(done.stdout[-2000:])
        sys.stderr.write(done.stderr[-2000:])
        return None
    return got


def bound(values, granule, stage, cap):
    top = max(values)
    spread = top - min(values)
    margin = max(3 * spread, top // 20, granule)
    held = top + margin
    band = False
    if stage == 'new' and cap > 0 and held > int(BAND * cap):
        held = int(BAND * cap)
        band = True
    return held, margin, band


def self_test():
    # A bound from three close takes of the ring and its copy (about twice a
    # 2 MiB cap) passes those takes and fails a second copy and a doubling.
    cap = 2097152
    takes = [4300000, 4310000, 4325000]
    held, _, band = bound(takes, 262144, 'new', cap)
    assert not band and max(takes) <= held < 3 * cap, held
    assert 2 * max(takes) > held and 3 * cap > held
    # A wide spread cannot widen a `new` bound past the band.
    held, _, band = bound([4300000, 5000000, 5600000], 262144, 'new', cap)
    assert band and held == int(BAND * cap), held
    # The other stages have no band: a resize that made the ring again
    # (two caps more) fails a bound read from takes under 1 MB.
    held, _, band = bound([200000, 260000, 310000], 262144, 'resize', cap)
    assert not band and held < 2 * cap, held
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
            held.setdefault(key(stage, cap), []).append(increment)
    print('TAKES-JSON ' + json.dumps({host: held}, sort_keys=True))
    if args.measure:
        return 0
    recorded = json.loads(args.takes_file.read_text()) if args.takes_file.exists() else {}
    failed = 0
    rows = 0
    if host not in recorded:
        print('FAIL ring-resident host=%s: no recorded takes in %s' % (host, args.takes_file.name))
        print('RING-RESIDENT rows=1 failed=1')
        return 1
    for stage, cap in pairs():
        rows += 1
        name = key(stage, cap)
        takes = recorded[host].get(name)
        if not takes:
            print('FAIL ring-resident %s cap=%d: no recorded takes for host=%s' % (stage, cap, host))
            failed += 1
            continue
        limit, margin, band = bound(takes, granule, stage, cap)
        worst = max(held[name])
        how = 'band %.1fx' % BAND if band else 'margin %d' % margin
        if worst > limit:
            ratio = ' (ratio %.2fx, bound %.2fx)' % (worst / cap, limit / cap) if cap else ''
            print('FAIL ring-resident %s cap=%d increment=%d past bound=%d%s; recorded %s, %s'
                  % (stage, cap, worst, limit, ratio, takes, how))
            failed += 1
        else:
            print('PASS ring-resident %s cap=%d increment=%d bound=%d; recorded %s, %s' % (stage, cap, worst, limit, takes, how))
    rows += 1
    if projection is None:
        print('FAIL ring-resident projection: the probe printed none')
        failed += 1
    else:
        history_bytes, pane_bytes = projection
        measured = max(held[key('new', history_bytes)]) if key('new', history_bytes) in held else None
        if measured is None:
            print('FAIL ring-resident projection: no `new` row at the server\'s cap %d' % history_bytes)
            failed += 1
        elif pane_bytes < measured:
            print('FAIL ring-resident projection pane-bytes-80x24=%d under the measured %d' % (pane_bytes, measured))
            failed += 1
        else:
            print('PASS ring-resident projection pane-bytes-80x24=%d measured=%d over=%.2fx'
                  % (pane_bytes, measured, pane_bytes / measured))
    print('RING-RESIDENT rows=%d failed=%d' % (rows, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
