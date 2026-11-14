#!/usr/bin/env python3
"""Run the layout rows in slices on the checked machine or under lupin, and sum them.

Each run is `src/layout_slice.lu`: once with no arguments (every golden), then
`SIZE FIRST COUNT` slices covering sequences 0..N-1 at each of the five sizes.
A checked run counts only when its observation record says exit(0) at the
`run` phase, from the pinned compiler, with no diagnostic or warning; its
command exit alone is never a verdict. A lupin run counts on exit 0 under an
address-space cap. Every row must be checked at least once at every size.
"""
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import tomllib

SIZES = ('20x6', '80x24', '81x25', '320x90', '512x512')
PLAN = {'checked': (200, 10), 'lupin': (50, 25)}
GOLDENS = 59


def cap():
    limit = 6 * 1024 * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def observe(mode, args, pin):
    if mode == 'checked':
        argv = ['layout_slice'] + args
        command = [os.environ['WOLF'], 'conform-run', 'src/layout_slice.lu', '--checked', '--json',
                   '--deny-warnings'] + ['--argv-hex=' + a.encode().hex() for a in argv]
        result = subprocess.run(command, capture_output=True, timeout=600)
        if result.returncode:
            return None, 'observation command exit=%d' % result.returncode
        record = json.loads(result.stdout)
        commit = record.get('commit') or ''
        if record.get('impl') != 'wolfgang' or record.get('impl_version') != pin['version'] or \
                not commit or not pin['rev'].startswith(commit):
            return None, 'not the pinned compiler'
        if record.get('diagnostics') or record.get('warnings'):
            return None, 'diagnostics or warnings'
        text = record.get('stdout_inline') or ''
        if record.get('verdict') != 'exit(0)' or record.get('phase_reached') != 'run':
            return text, 'verdict=%s phase=%s why=%s' % (record.get('verdict'), record.get('phase_reached'),
                                                       record.get('x-unsupported-construct'))
        return text, None
    command = [os.environ['LUPIN'], 'run', 'src/layout_slice.lu'] + args
    result = subprocess.run(command, capture_output=True, timeout=1800, preexec_fn=cap)
    text = result.stdout.decode('utf-8', 'replace')
    if result.returncode:
        return text, 'lupin exit=%d %s' % (result.returncode, result.stderr.decode('utf-8', 'replace')[-300:])
    return text, None


def main():
    mode = sys.argv[1]
    total, chunk = PLAN[mode]
    pin = tomllib.loads(Path('wolf-toolchain.toml').read_text())['wolf']
    failed = 0
    text, why = observe(mode, [], pin)
    lines = (text or '').splitlines()
    passed = sum(1 for l in lines if l.startswith('PASS layout-golden-'))
    for line in lines:
        if line.startswith('FAIL '):
            print(line, flush=True)
    if why or passed != GOLDENS or 'LAYOUT-GOLDENS cases=%d failed=0' % GOLDENS not in lines:
        print('FAIL layout-%s-goldens passed=%d of %d %s' % (mode, passed, GOLDENS, why or ''), flush=True)
        failed += 1
    else:
        print('PASS layout-%s-goldens cases=%d' % (mode, passed), flush=True)
    for index, size in enumerate(SIZES):
        sums = {}
        runs = 0
        first = 0
        while first < total:
            count = min(chunk, total - first)
            text, why = observe(mode, [str(index), str(first), str(count)], pin)
            runs += 1
            for line in (text or '').splitlines():
                word = line.split()
                if line.startswith('FAIL '):
                    print(line, flush=True)
                    failed += 1
                elif len(word) > 1 and word[0] in ('PASS', 'INFO') and word[1].startswith('layout-') and \
                        word[1] != 'layout-ops':
                    checks = [w for w in word if w.startswith('checks=')]
                    sums[word[1]] = sums.get(word[1], 0) + (int(checks[0][7:]) if checks else 0)
            if why:
                print('FAIL layout-%s-slice size=%s sequences=%d..%d %s' % (mode, size, first, first + count - 1, why),
                      flush=True)
                failed += 1
            first += count
        for row in ('layout-refusal-unchanged', 'layout-inv1-tiling', 'layout-inv2-structure', 'layout-inv3-shares',
                    'layout-inv4-split-close', 'layout-inv5-resize-back', 'layout-inv6-focus-back'):
            if sums.get(row, 0) < 1:
                print('FAIL %s size=%s %s never-exercised' % (row, size, mode), flush=True)
                failed += 1
            else:
                print('PASS %s size=%s %s sequences=0..%d runs=%d checks=%d' % (row, size, mode, total - 1, runs,
                                                                               sums[row]), flush=True)
    print('LAYOUT-%s sizes=5 sequences-per-size=%d slice=%d failed=%d' % (mode.upper(), total, chunk, failed))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
