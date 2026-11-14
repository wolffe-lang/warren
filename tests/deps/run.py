#!/usr/bin/env python3
"""Run the dependency rows on one host and hold their lines to expect.txt.

Each row is one program in its own directory (tests/deps/<row>/main.lu).
Tiers: native (a build with the given wolf and std, run in a scratch
directory of its own), checked (`wolf conform-run --json --checked`, never
a native fallback) and lupin (its refusal is held by builtin name). Every
run has a wall bound; a row that outlives it is red, never retried.

A row's expected lines live in tests/deps/expect.txt under headers
`[row tier host]`, where host is linux, darwin, pax or `*`. The most
specific header wins. `refuses=NAME` expects a named refusal instead of
output. Lines are compared exactly and in order; a missing header is red.

Prints `PASS deps <row> <tier>` or `FAIL deps <row> <tier>: <why>` and a
closing `DEPS rows=N failed=M`; exits 1 when any row is red.
"""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROWS = ('one_wait', 'partial_write', 'start_lock', 'peer_cred', 'daemon')


def expectations():
    table = {}
    key = None
    for raw in (HERE / 'expect.txt').read_text().splitlines():
        line = raw.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        if line.startswith('[') and line.endswith(']'):
            key = tuple(line[1:-1].split())
            if len(key) != 3:
                raise ValueError('bad header %r' % line)
            table[key] = []
        elif key is None:
            raise ValueError('line before any header: %r' % line)
        else:
            table[key].append(line)
    return table


def expected(table, row, tier, host):
    for key in ((row, tier, host), (row, tier, '*')):
        if key in table:
            return table[key]
    return None


def compare(got, want):
    lines = got.splitlines()
    if lines == want:
        return None
    for i in range(max(len(lines), len(want))):
        a = lines[i] if i < len(lines) else '<missing>'
        b = want[i] if i < len(want) else '<missing>'
        if a != b:
            return 'line %d: got %r, want %r' % (i + 1, a, b)
    return 'differs'


def scratch(out, row, tier):
    d = out / 'run' / ('%s-%s' % (row, tier))
    if d.exists():
        shutil.rmtree(d)
    d.mkdir(parents=True)
    return d


def run(command, cwd, bound, env=None):
    try:
        p = subprocess.run(command, cwd=cwd, capture_output=True, timeout=bound, env=env)
    except subprocess.TimeoutExpired:
        return None
    return p


def native(args, row, out):
    exe = out / 'bin' / row
    exe.parent.mkdir(parents=True, exist_ok=True)
    build = [args.wolf, 'build', '--deny-warnings', '--std-root', args.std, str(HERE / row / 'main.lu'), '-o', str(exe)]
    p = run(build, HERE / row, 600)
    if p is None or p.returncode:
        return None, 'build exit=%s %s' % (None if p is None else p.returncode,
                                            (p.stderr.decode(errors='replace')[-600:] if p else 'timeout'))
    if args.build_only:
        return '', None
    d = scratch(out, row, 'native')
    p = run([str(exe)], d, args.bound)
    if p is None:
        return None, 'timeout after %ss' % args.bound
    (out / ('%s-native.stderr' % row)).write_bytes(p.stderr)
    sys.stdout.write(''.join('  | %s\n' % l for l in p.stderr.decode(errors='replace').splitlines()))
    if p.returncode:
        return None, 'exit=%d stdout=%r stderr=%r' % (p.returncode, p.stdout.decode(errors='replace')[-400:],
                                                      p.stderr.decode(errors='replace')[-400:])
    return p.stdout.decode(errors='replace'), None


def checked(args, row, out):
    d = scratch(out, row, 'checked')
    shutil.copy(HERE / row / 'main.lu', d / 'main.lu')
    p = run([args.wolf, 'conform-run', 'main.lu', '--json', '--checked', '--deny-warnings', '--std-root', args.std],
            d, args.bound)
    if p is None:
        return None, 'timeout after %ss' % args.bound
    (out / ('%s-checked.json' % row)).write_bytes(p.stdout)
    try:
        record = json.loads(p.stdout)
    except ValueError:
        return None, 'not json: %r %r' % (p.stdout[-300:], p.stderr[-300:])
    if record.get('phase_reached') != 'run' or record.get('verdict') != 'exit(0)':
        return None, 'checked verdict=%r phase=%r unsupported=%r' % (
            record.get('verdict'), record.get('phase_reached'), record.get('x-unsupported-at', record.get('unsupported')))
    return record.get('stdout', ''), None


def lupin(args, row, out, want):
    d = scratch(out, row, 'lupin')
    shutil.copy(HERE / row / 'main.lu', d / 'main.lu')
    env = dict(os.environ, LUPIN_STD=args.std)
    p = run([args.lupin, 'run', 'main.lu'], d, args.bound, env)
    if p is None:
        return None, 'timeout after %ss' % args.bound
    text = (p.stdout + p.stderr).decode(errors='replace')
    (out / ('%s-lupin.txt' % row)).write_text(text)
    names = [w[len('refuses='):] for w in want if w.startswith('refuses=')]
    if names:
        if p.returncode == 0:
            return None, 'lupin ran to exit 0; expected a refusal naming %s' % names[0]
        if names[0] not in text:
            return None, 'lupin exit=%d without %s: %r' % (p.returncode, names[0], text[-400:])
        return '\n'.join(want), None
    if p.returncode:
        return None, 'lupin exit=%d %r' % (p.returncode, text[-400:])
    return p.stdout.decode(errors='replace'), None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wolf', required=True)
    parser.add_argument('--lupin')
    parser.add_argument('--std', required=True)
    parser.add_argument('--host', default='darwin' if platform.system() == 'Darwin' else 'linux')
    parser.add_argument('--tiers', default='native,checked,lupin')
    parser.add_argument('--rows', default=','.join(ROWS))
    parser.add_argument('--out', type=Path, default=HERE.parents[1] / 'target' / 'deps')
    parser.add_argument('--bound', type=int, default=120, help='seconds per run')
    parser.add_argument('--build-only', action='store_true', help='build native binaries, run nothing')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    table = expectations()
    failed = total = 0
    for row in args.rows.split(','):
        for tier in args.tiers.split(','):
            if args.build_only and tier != 'native':
                continue
            total += 1
            want = expected(table, row, tier, args.host)
            if want is None and not args.build_only:
                failed += 1
                print('FAIL deps %s %s: no expectation for host %s' % (row, tier, args.host), flush=True)
                continue
            if tier == 'native':
                got, why = native(args, row, args.out)
            elif tier == 'checked':
                got, why = checked(args, row, args.out)
            elif tier == 'lupin':
                got, why = lupin(args, row, args.out, want)
            else:
                got, why = None, 'unknown tier'
            if why is None and not args.build_only:
                why = compare(got, want)
            if why is not None:
                failed += 1
                print('FAIL deps %s %s: %s' % (row, tier, why), flush=True)
            else:
                print('PASS deps %s %s' % (row, tier), flush=True)
                for line in (got or '').splitlines():
                    print('  %s' % line)
    print('DEPS rows=%d failed=%d host=%s' % (total, failed, args.host))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())
