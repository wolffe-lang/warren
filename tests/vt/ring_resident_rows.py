#!/usr/bin/env python3
"""warren#67: one pane's resident cost, measured and held.

    ring_resident_rows.py [--measure] [--takes N] [--takes-file FILE] MEASURE_CHILD RING_PROBE

Each stage of ring-probe (src/ring_probe.lu) runs in a process of its own,
spawned by measure-child, the small C parent: `none` once a take, then `new`,
`resize`, `screenful` and `filled` at history caps of 0, 2 MiB and 8 MiB
(`filled` only where there is a ring), every pair TAKES times (3). Then the
panes stages, `panes-idle` and `panes-written` with 1, 8 and 32 panes, each at
cap 0 and at the server's cap (2 MiB).

Every run prints, raw, measure-child's peak, the floor it reports (the C
child's high-water mark before exec, which ru_maxrss keeps across exec; it
reads 0 in some runs on Linux, and is never used in arithmetic) and the
parent's own peak, the same take's `none` peak, and, where the host has
/proc, the probe's last VmRSS and VmHWM. Nothing is subtracted without being
printed. The quantity a row holds is printed beside its formula:
  new                          increment = peak(new, CAP) - peak(none)
  resize, screenful, filled    increment = peak(STAGE, CAP) - peak(new, CAP)
  panes-KIND-N at cap 0        increment = peak(panes, 0) - peak(none)
  panes-KIND-N at the cap      increment = peak(panes, CAP) - peak(panes, 0)
each within one take, and `ratio = increment / CAP` where CAP > 0. A `new`
increment carries what the first pane in a fresh process pays once (the
emulator's code paged in, the allocator's first chunk) as well as the pane.

A row holds one number from its takes: the least peak of its stage less the
least peak of its base, the least on both sides of the subtraction. The
program is the same in every take, and a host may peak a few pages higher in
one of them: on hosted macOS runners one take of three peaked 8 to 11 pages
(128 to 176 KiB) higher, on either side of a subtraction, four times in the
96 runs of four hosted jobs at caps 0 and 2 MiB, and by one or two pages a few
times more, while the least of each row's takes moved by at most two pages
from job to job. A cost the program pays in every take is in the least; one
take's wobble is not.

The bound of a row is read from the takes recorded for this host in
tests/vt/ring-resident-takes.json: the same number from the recorded takes,
plus a margin that is the largest of three times the recorded takes' spread,
5% of the largest recorded peak of that stage, or one allocation granule
(256 KiB on Linux, 16 KiB on macOS). A `resize` row above cap 0 is held to at
least the bound of `resize` at cap 0: a first resize costs the same at every
cap, and whether a cap's takes show that cost is the allocator's (on Linux and
macOS 15 it hides under the peak the ring's creation set; on macOS 26 it does
not, warren#88), so allocator reuse can lower a reading but cannot set its
bound. The rule checks itself where a ring is made, on the room between a
bound and its takes' number: a `new` row's room must be under one cap, so one
more cap-sized buffer at the peak fails; a `filled` row's too, since a filled
ring is one cap and a second copy of it must fail; another difference row's
room must be under two caps, so a step that made the ring again fails. A room past that fails by
name as too loose. A host
with no recorded takes fails by name. A cap a host does not hold (macOS at
8 MiB, whose allocator's peak there is bimodal) is measured, printed and named
in a NOTE with its takes, and holds nothing. Each verdict names its row: `ring-resident-STAGE`
(new, resize, screenful, filled), `ring-resident-panes`, `ring-resident-projection`,
`ring-resident-takes` and `ring-resident-probe`.

The panes rows hold what N panes' rings cost to the history they hold. Their
number is the least peak of N panes at the server's cap less the least peak of
the same N panes at cap 0 (no ring). Its bound is the history written, each
pane's `history-used` (printed by the probe, the same in every take) rounded
up to whole pages of this host, plus two pages for each ring that holds a
record (a reservation's own pages, measured untouched), plus the margin rule
above over this pair's recorded takes. A margin of one cap or more is too
loose: one pane whose ring is made whole must fail at every N. The cap-0 runs
are the rows' bases, printed and not held.

The projection row holds the server's projection of an 80x24 pane
(`pane_bytes`, printed by the probe) at or above the largest increment of a
filled ring over `none` at the server's history cap (a pane's worst case: its
ring written to the cap), and prints how far above.

Every run ends its measurements with one `TAKES-JSON` line for this host, in
the form the takes file records; --measure stops there and holds nothing.
Exit 0 when every row holds, 1 when one does not, 2 on a probe that did not
run.
"""
import argparse
import json
import os
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
# The panes stages: how many panes, and the cap they are held at (the server's,
# HISTORY_BYTES); each is also run at cap 0, its base.
PANES = (1, 8, 32)
PANE_KINDS = ('panes-idle', 'panes-written')
PANES_CAP = 2097152
# Pages a ring's reservation costs beside what is written in it: an untouched
# 2 MiB reserve measured 2 pages on macOS arm64 (16 KiB pages).
RING_PAGES = 2
PAGE = os.sysconf('SC_PAGE_SIZE')
TAKES_FILE = Path(__file__).with_name('ring-resident-takes.json')
MEASURE = re.compile(r'^MEASURE process exit=(\d+) signal=(\d+) wall-nanoseconds=(\d+) peak-rss-bytes=(\d+) '
                     r'child-before-exec-peak-rss-bytes=(-?\d+) parent-inherited-peak-rss-bytes=(-?\d+) ')
STEP = re.compile(r'^RING-PROBE stage=\S+ cap=\d+ step=(\S+) vmrss-kb=(-?\d+) vmhwm-kb=(-?\d+) '
                  r'history-used=(\d+) history-evicted=(\d+)$')
PROJECTION = re.compile(r'^RING-PROBE-PROJECTION history-bytes=(\d+) pane-bytes-80x24=(\d+)$')
PANES_LINE = re.compile(r'^RING-PROBE-PANES stage=\S+ cap=\d+ n=(\d+) used=([\d,]+)$')


def this_host():
    return 'macos' if sys.platform == 'darwin' else 'linux'


def pairs():
    for cap in CAPS:
        for stage in STAGES:
            if stage == 'filled' and cap == 0:
                continue
            yield stage, cap


def pane_pairs():
    """(kind, n), each run at cap 0 and then at PANES_CAP."""
    for kind in PANE_KINDS:
        for n in PANES:
            yield kind, n


def key(stage, cap):
    return '%s %d' % (stage, cap)


def pane_key(kind, n, cap):
    return '%s-%d %d' % (kind, n, cap)


def run(measure_child, probe, stage, cap, n=None):
    command = [measure_child, probe, stage, str(cap)] + ([str(n)] if n is not None else [])
    done = subprocess.run(command, capture_output=True, text=True, errors='replace', timeout=900)
    got = {'exit': None, 'step': '-', 'vmrss': -1, 'vmhwm': -1, 'projection': None, 'each': None}
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
        m = PANES_LINE.match(line)
        if m and int(m.group(1)) == n:
            got['each'] = [int(u) for u in m.group(2).split(',')]
    last = 'start' if stage == 'none' else stage
    if got['exit'] != 0 or got['step'] != last or (n is not None and (got['each'] is None or len(got['each']) != n)):
        print('FAIL ring-resident-probe %s cap=%d: exit %s at step %s' % (stage, cap, got['exit'], got['step']))
        sys.stdout.write(done.stdout[-2000:])
        sys.stderr.write(done.stderr[-2000:])
        return None
    return got


def held_increment(peaks, bases):
    """A row's number from its takes: the least peak of the stage less the
    least peak of its base (`none` for `new`, else `new` at the cap). A
    take that peaks a few pages higher on one side is the host's and drops
    out; a cost the program pays in every take stays in."""
    return min(peaks) - min(bases)


def bases_of(increments, peaks):
    """Each take's base, from its peak and increment as recorded."""
    return [p - i for p, i in zip(peaks, increments)]


def bound(increments, peaks, granule):
    """The bound and its margin: the recorded takes' number, plus the
    largest of three times their spread, 5% of their largest peak, or a
    granule."""
    top = held_increment(peaks, bases_of(increments, peaks))
    spread = max(increments) - min(increments)
    margin = max(3 * spread, max(peaks) // 20, granule)
    return top + margin, margin


def written_pages(each, page):
    """The history the panes hold, each pane's rounded up to whole pages, and
    how many rings hold any."""
    return sum((u + page - 1) // page * page for u in each), sum(1 for u in each if u > 0)


def panes_bound(each, page, increments, peaks, granule):
    """A panes row's bound: what is written, two pages a ring that holds a
    record, and the margin rule over the recorded takes."""
    written, rings = written_pages(each, page)
    spread = max(increments) - min(increments)
    margin = max(3 * spread, max(peaks) // 20, granule)
    return written + rings * RING_PAGES * page + margin, margin, written, rings


def row_bound(pairs, stage, cap, granule):
    """A row's bound from the takes recorded for its host (`pairs`, as the
    takes file keys them), its room (how far the bound sits above the
    recorded takes' own number) and the cap-0 bound where that set it, else
    None. A first resize costs the same at every cap, and whether a cap's
    takes show that cost is the allocator's (warren#88): so a `resize` row
    above cap 0 is held to at least the bound of `resize` at cap 0, and
    allocator reuse can lower a reading but cannot set its bound."""
    takes = pairs[key(stage, cap)]
    limit, margin = bound(takes['increments'], takes['peaks'], granule)
    own = limit - margin
    base = pairs.get(key('resize', 0))
    if stage == 'resize' and cap > 0 and base:
        cap0, _ = bound(base['increments'], base['peaks'], granule)
        if cap0 > limit:
            return cap0, cap0 - own, cap0
    return limit, margin, None


def too_loose(stage, cap, room):
    """Why a bound's room over its takes' number cannot see what its row is
    for, or None."""
    if cap == 0:
        return None
    if stage == 'new' and room >= cap:
        return 'room %d is not under one cap (%d): one more cap-sized buffer at the peak would pass' % (room, cap)
    if stage == 'filled' and room >= cap:
        return 'room %d is not under one cap (%d): a second copy of the filled ring would pass' % (room, cap)
    if stage == 'panes' and room >= cap:
        return 'room %d is not under one cap (%d): one pane\'s ring made whole would pass' % (room, cap)
    if stage != 'new' and room >= 2 * cap:
        return 'room %d is not under two caps (%d): a step that made the ring again would pass' % (room, 2 * cap)
    return None


def self_test():
    """The rule on fixed takes; a FAIL line names each case it breaks."""
    fails = []

    def check(name, ok, detail):
        if not ok:
            fails.append(name)
            print('FAIL ring-resident-self-test %s: %s' % (name, detail))

    cap = 2097152
    granule = 262144
    # Close takes of a pane at about 3.7 caps: the takes pass, one more cap fails.
    inc = [7471104, 7720960, 7872512]
    peaks = [10055680, 10268672, 10347520]
    held, margin = bound(inc, peaks, granule)
    check('close-takes', max(inc) <= held < max(inc) + cap and too_loose('new', cap, margin) is None,
          'bound %d margin %d' % (held, margin))
    # A spread that wide cannot hold a `new` row: the rule says so by name.
    _, margin = bound([7000000, 7800000, 8600000], peaks, granule)
    check('too-loose', too_loose('new', cap, margin) is not None, 'margin %d passed' % margin)
    # A difference row: noise of half a megabyte passes, the ring made again (two caps) fails.
    held, margin = bound([-544768, 147456, 229376], [9723904, 10285056, 10244096], granule)
    check('difference-noise', 229376 <= held < 2 * cap and too_loose('resize', cap, margin) is None,
          'bound %d margin %d' % (held, margin))
    # macOS, hosted: one take of three peaked ten pages higher than the other
    # two and than every recorded take (screenful at cap 0, trunk's push run
    # 45069173446). One take's wobble is the host's: the row holds.
    recorded = [278528, 278528, 278528]
    limit, _ = bound(recorded, [2277376, 2277376, 2277376], 16384)
    peaks = [2277376, 2277376, 2441216]
    got = held_increment(peaks, [1998848, 1998848, 1998848])
    check('one-take-wobble', got <= limit, 'held %d past bound %d' % (got, limit))
    # The base wobbles instead (`none` eleven pages higher in one take): the
    # row's number is the pane's, not lowered or raised by it.
    got = held_increment([1998848, 1998848, 1998848], [1556480, 1736704, 1556480])
    check('base-wobble', got == 442368, 'held %d, not 442368' % got)
    # A cost paid in every take (one more cap-sized buffer at `new`) fails.
    limit, _ = bound([6750208, 6750208, 6750208], [8306688, 8306688, 8306688], 16384)
    got = held_increment([8306688 + cap] * 3, [1556480] * 3)
    check('every-take-cost', got > limit, 'held %d within bound %d' % (got, limit))
    # macOS 26: the creation's freed buffers stay resident, so a first resize
    # pays its whole cost at the 2 MiB cap as at cap 0 (warren#88). Against
    # the macOS 15 takes, which hid most of it, that reading holds: a resize
    # row is held to at least its cap-0 bound.
    mac15 = {'resize 0': {'increments': [1966080] * 3, 'peaks': [3964928] * 3},
             'resize 2097152': {'increments': [344064] * 3, 'peaks': [8650752] * 3}}
    limit, room, _ = row_bound(mac15, 'resize', cap, 16384)
    got = held_increment([10551296] * 3, [8601600] * 3)
    check('resize-held-to-cap0', got <= limit and too_loose('resize', cap, room) is None,
          'held %d, bound %d, room %d' % (got, limit, room))
    # The cap-0 bound does not pass a resize that made the ring again: two caps
    # over the row's own number fails.
    got = held_increment([8650752 + 2 * cap] * 3, [8306688] * 3)
    check('resize-cap0-ring-again', got > limit, 'held %d within bound %d' % (got, limit))
    # A cap-0 bound two caps or more above a row's own number is too loose, by name.
    wide = {'resize 0': {'increments': [4400000] * 3, 'peaks': [6400000] * 3},
            'resize 2097152': {'increments': [0] * 3, 'peaks': [8650752] * 3}}
    _, room, _ = row_bound(wide, 'resize', cap, 16384)
    check('cap0-too-loose', too_loose('resize', cap, room) is not None, 'room %d passed' % room)
    # 32 panes of 264,132 bytes of history each, 16 KiB pages: 17 pages a pane.
    each = [264132] * 32
    written, rings = written_pages(each, 16384)
    check('panes-written-pages', (written, rings) == (32 * 278528, 32), 'written %d rings %d' % (written, rings))
    limit, margin, _, _ = panes_bound(each, 16384, [9961472] * 3, [30638080] * 3, 16384)
    check('panes-written-bound', 9961472 <= limit and too_loose('panes', cap, margin) is None,
          'bound %d margin %d' % (limit, margin))
    # Rings that double as they grow keep about three times what they hold.
    check('panes-doubling', 3 * written > limit, 'bound %d holds %d' % (limit, 3 * written))
    # One pane's ring made whole, at 32 panes: one cap more, red.
    check('panes-ring-whole', 9961472 + cap > limit, 'bound %d holds %d' % (limit, 9961472 + cap))
    # One take of three eleven pages high on the cap side holds.
    got = held_increment([30638080, 30638080, 30638080 + 11 * 16384], [20676608] * 3)
    check('panes-one-take-wobble', got <= limit, 'held %d past bound %d' % (got, limit))
    # No history: the bound is the margin alone, and an idle ring made whole fails.
    limit, margin, written, rings = panes_bound([0] * 32, 16384, [0] * 3, [20463616] * 3, 16384)
    check('panes-idle', written == 0 and rings == 0 and limit == margin < cap, 'bound %d margin %d' % (limit, margin))
    # A filled ring at one cap over `new` holds; a second copy of it fails.
    limit, margin = bound([2375680] * 3, [4882432] * 3, 16384)
    check('filled-one-cap', 2375680 <= limit and too_loose('filled', cap, margin) is None,
          'bound %d margin %d' % (limit, margin))
    check('filled-two-caps', 2375680 + cap > limit, 'bound %d holds %d' % (limit, 2375680 + cap))
    _, margin = bound([1600000, 2000000, 2400000], [4882432] * 3, 16384)
    check('filled-too-loose', too_loose('filled', cap, margin) is not None, 'margin %d passed' % margin)
    if not fails:
        print('PASS ring-resident-self-test')
    return not fails


def main():
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument('--measure', action='store_true')
    p.add_argument('--takes', type=int, default=3)
    p.add_argument('--takes-file', type=Path, default=TAKES_FILE)
    p.add_argument('measure_child')
    p.add_argument('probe')
    args = p.parse_args()
    if not self_test():
        print('RING-RESIDENT rows=1 failed=1')
        return 1
    host = this_host()
    granule = GRANULE[host]
    held = {}
    each = {}
    nones = []
    filled = []
    projection = None
    for take in range(1, args.takes + 1):
        none = run(args.measure_child, args.probe, 'none', 0)
        if none is None:
            return 2
        projection = none['projection']
        nones.append(none['peak'])
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
            if stage == 'filled' and projection is not None and cap == projection[0]:
                filled.append(got['peak'])
        for kind, n in pane_pairs():
            base_peak = none['peak']
            for cap in (0, PANES_CAP):
                got = run(args.measure_child, args.probe, kind, cap, n)
                if got is None:
                    return 2
                name = pane_key(kind, n, cap)
                if name in each and each[name] != got['each']:
                    print('FAIL ring-resident-probe %s cap=%d: history used %s, not %s as in take 1'
                          % (name, cap, got['each'], each[name]))
                    return 2
                each[name] = got['each']
                formula = 'peak(%s-%d, 0) - peak(none)' % (kind, n) if cap == 0 else \
                    'peak(%s-%d, %d) - peak(%s-%d, 0)' % (kind, n, cap, kind, n)
                increment = got['peak'] - base_peak
                print('MEASURE ring-resident host=%s stage=%s-%d cap=%d take=%d peak=%d floor=%d parent=%d none=%d '
                      'increment=%d history-used=%d vmrss-kb=%d vmhwm-kb=%d formula="%s"'
                      % (host, kind, n, cap, take, got['peak'], got['floor'], got['parent'], none['peak'], increment,
                         sum(got['each']), got['vmrss'], got['vmhwm'], formula))
                row = held.setdefault(name, {'increments': [], 'peaks': []})
                row['increments'].append(increment)
                row['peaks'].append(got['peak'])
                base_peak = got['peak']
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
        limit, room, cap0 = row_bound(recorded[host]['pairs'], stage, cap, granule)
        loose = too_loose(stage, cap, room)
        held_to = '; held to resize cap 0\'s bound %d' % cap0 if cap0 is not None else ''
        peaks = held[name]['peaks']
        bases = bases_of(held[name]['increments'], peaks)
        worst = held_increment(peaks, bases)
        ratio = ' (ratio %.2fx, bound %.2fx)' % (worst / cap, limit / cap) if cap else ''
        # The increment held is the least peak less the least base, which
        # may come from different takes, so it need not be any one take's
        # increment: the line prints both leasts and each take's increment.
        held_from = 'least peak %d less least base %d; takes\' increments %s' % (min(peaks), min(bases),
                                                                               held[name]['increments'])
        if loose:
            print('FAIL ring-resident-%s cap=%d: bound too loose: %s' % (stage, cap, loose))
            failed += 1
        elif worst > limit:
            print('FAIL ring-resident-%s cap=%d increment=%d past bound=%d%s (%s); recorded %s, room %d%s'
                  % (stage, cap, worst, limit, ratio, held_from, takes['increments'], room, held_to))
            failed += 1
        else:
            print('PASS ring-resident-%s cap=%d increment=%d bound=%d%s (%s); room %d%s'
                  % (stage, cap, worst, limit, ratio, held_from, room, held_to))
    for kind, n in pane_pairs():
        base = pane_key(kind, n, 0)
        print('NOTE ring-resident-panes kind=%s n=%d cap=0 host=%s: the base, measured, not held; increments %s'
              % (kind[6:], n, host, held[base]['increments']))
        name = pane_key(kind, n, PANES_CAP)
        if PANES_CAP not in HELD_CAPS[host]:
            continue
        rows += 1
        takes = recorded[host]['pairs'].get(name)
        if not takes:
            print('FAIL ring-resident-panes kind=%s n=%d cap=%d: no recorded takes for host=%s'
                  % (kind[6:], n, PANES_CAP, host))
            failed += 1
            continue
        limit, margin, written, rings = panes_bound(each[name], PAGE, takes['increments'], takes['peaks'], granule)
        loose = too_loose('panes', PANES_CAP, margin)
        growth = held_increment(held[name]['peaks'], held[base]['peaks'])
        shown = ('growth=%d written=%d rings=%d page=%d bound=%d (least peak %d less least base %d; takes\' '
                 'growth %s); margin %d' % (growth, written, rings, PAGE, limit, min(held[name]['peaks']),
                                           min(held[base]['peaks']), held[name]['increments'], margin))
        if loose:
            print('FAIL ring-resident-panes kind=%s n=%d cap=%d: bound too loose: %s' % (kind[6:], n, PANES_CAP, loose))
            failed += 1
        elif growth > limit:
            print('FAIL ring-resident-panes kind=%s n=%d cap=%d %s; past the bound by %d; recorded %s'
                  % (kind[6:], n, PANES_CAP, shown, growth - limit, takes['increments']))
            failed += 1
        else:
            print('PASS ring-resident-panes kind=%s n=%d cap=%d %s' % (kind[6:], n, PANES_CAP, shown))
    rows += 1
    if projection is None:
        print('FAIL ring-resident-projection: the probe printed none')
        failed += 1
    else:
        history_bytes, pane_bytes = projection
        if len(filled) != len(nones):
            print('FAIL ring-resident-projection: no `filled` row at the server\'s cap %d' % history_bytes)
            failed += 1
        else:
            measured = max(f - z for f, z in zip(filled, nones))
            if pane_bytes < measured:
                print('FAIL ring-resident-projection pane-bytes-80x24=%d under the measured %d (a filled ring over none)'
                      % (pane_bytes, measured))
                failed += 1
            else:
                print('PASS ring-resident-projection pane-bytes-80x24=%d measured=%d over=%.2fx (a filled ring over none)'
                      % (pane_bytes, measured, pane_bytes / measured))
    print('RING-RESIDENT rows=%d failed=%d' % (rows, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
