#!/usr/bin/env python3
"""The gate runs each large-screen row program under a stated peak.

    gate_peak_bound_rows.py

A row program that builds large screens runs under tools/vt/peak_bound.py over
measure-child, with its bound in bytes written on its gate step, so a program
that grows is a red row naming its peak rather than a kill (a 9.9 GB peak once
ended the hosted Linux job with exit 137 and no name). The check is also run
over altered copies of the gate, each of which it must refuse.
"""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
LARGE_SCREEN_STEPS = {
    'compose-native': 'compose-rows',
    'compose-damage-native': 'compose-damage',
    'client-spans-native': 'client-spans',
}
STEP = re.compile(
    r'^step (?P<step>\S+) python3 -I tools/vt/peak_bound\.py --name (?P<name>\S+) --bound (?P<bound>\d+) -- '
    r'"\$root/target/native/measure-child" "\$root/target/native/(?P<program>[a-z-]+)"(?P<rest>.*)$')


def problems(text):
    """Each large-screen step's problem, or none."""
    found = {}
    for line in text.splitlines():
        words = line.split()
        if len(words) > 1 and words[0] == 'step' and words[1] in LARGE_SCREEN_STEPS:
            found.setdefault(words[1], []).append(line)
    out = []
    for step, program in sorted(LARGE_SCREEN_STEPS.items()):
        lines = found.get(step, [])
        if len(lines) != 1:
            out.append('%s: %d gate steps by that name, expected one' % (step, len(lines)))
            continue
        m = STEP.match(lines[0])
        if not m:
            out.append('%s: not run under a stated bound: %s' % (step, lines[0]))
            continue
        if m.group('name') != step:
            out.append('%s: the wrapper names it %s' % (step, m.group('name')))
        if int(m.group('bound')) <= 0:
            out.append('%s: bound %s is not a positive byte count' % (step, m.group('bound')))
        if m.group('program') != program:
            out.append('%s: runs %s, expected %s' % (step, m.group('program'), program))
    return out


def main():
    text = (ROOT / 'tools/gate').read_text()
    failed = False
    # The check's own teeth: altered gates it must refuse.
    good = ('step compose-native python3 -I tools/vt/peak_bound.py --name compose-native --bound 536870912 -- '
            '"$root/target/native/measure-child" "$root/target/native/compose-rows"\n'
            'step compose-damage-native python3 -I tools/vt/peak_bound.py --name compose-damage-native --bound 1048576 -- '
            '"$root/target/native/measure-child" "$root/target/native/compose-damage" 12\n'
            'step client-spans-native python3 -I tools/vt/peak_bound.py --name client-spans-native --bound 1048576 -- '
            '"$root/target/native/measure-child" "$root/target/native/client-spans"\n')
    altered = {
        'unwrapped': good.replace('python3 -I tools/vt/peak_bound.py --name compose-native --bound 536870912 -- '
                                  '"$root/target/native/measure-child" ', ''),
        'zero-bound': good.replace('--bound 536870912', '--bound 0'),
        'wrong-name': good.replace('--name compose-native', '--name compose'),
        'wrong-program': good.replace('target/native/client-spans"', 'target/native/client-rows"'),
        'missing-step': '\n'.join(good.splitlines()[1:]) + '\n',
        'doubled-step': good + good.splitlines()[0] + '\n',
    }
    if problems(good):
        print('FAIL gate-peak-bound self-check: a correct gate is refused: %s' % problems(good))
        failed = True
    for name, variant in sorted(altered.items()):
        if problems(variant):
            print('PASS gate-peak-bound refuses %s' % name)
        else:
            print('FAIL gate-peak-bound self-check: the %s gate is accepted' % name)
            failed = True
    for problem in problems(text):
        print('FAIL gate-peak-bound %s' % problem)
        failed = True
    if failed:
        return 1
    print('PASS gate-peak-bound %s' % ' '.join(sorted(LARGE_SCREEN_STEPS)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
