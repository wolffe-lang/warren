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

`--transcript FILE` judges rows that ran elsewhere (PAX under QEMU): FILE
holds `ROW name`, the row's lines, `END name rc=N` per row, as the image's
script printed them on the console. A kernel's own narration (`PAX: ` lines,
a `user: ` tail) is dropped first; a row's stderr lines are those whose key
its expectation does not name.

Prints `PASS deps <row> <tier>` or `FAIL deps <row> <tier>: <why>` and a
closing `DEPS rows=N failed=M`; exits 1 when any row is red.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ROWS = ('one_wait', 'partial_write', 'start_lock', 'peer_cred', 'daemon', 'vt_api')
# Rows that are entries of warren's own package run from the repository
# root with their package; the others are standalone programs.
IN_PACKAGE = {'vt_api': 'src/vt_api_test.lu'}


def source(row):
    """(directory to run the build from, the entry's path from there)."""
    if row in IN_PACKAGE:
        return ROOT, IN_PACKAGE[row]
    return HERE / row, 'main.lu'


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
    # A super-user's run may measure what others cannot (a second uid);
    # its own header comes first when there is one.
    keys = [(row, tier, host), (row, tier, '*')]
    if os.geteuid() == 0:
        keys.insert(0, (row, tier, host + '-root'))
    for key in keys:
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
    where, entry = source(row)
    build = [args.wolf, 'build', '--deny-warnings', '--std-root', args.std, entry, '-o', str(exe)]
    p = run(build, where, 600)
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
    d, entry = source(row)
    if row not in IN_PACKAGE:
        d = scratch(out, row, 'checked')
        shutil.copy(HERE / row / 'main.lu', d / 'main.lu')
    p = run([args.wolf, 'conform-run', entry, '--json', '--checked', '--deny-warnings', '--std-root', args.std],
            d, args.bound)
    if p is None:
        return None, 'timeout after %ss' % args.bound
    (out / ('%s-checked.json' % row)).write_bytes(p.stdout)
    try:
        record = json.loads(p.stdout)
    except ValueError:
        return None, 'not json: %r %r' % (p.stdout[-300:], p.stderr[-300:])
    if record.get('protocol') != 1 or record.get('impl') != 'wolfgang':
        return None, 'not the checked machine: %r' % {k: record.get(k) for k in ('protocol', 'impl')}
    if record.get('phase_reached') != 'run' or record.get('verdict') != 'exit(0)':
        return None, 'checked verdict=%r phase=%r unsupported=%r' % (
            record.get('verdict'), record.get('phase_reached'), record.get('x-unsupported-at', record.get('unsupported')))
    if record.get('diagnostics') or record.get('warnings'):
        return None, 'checked observation has diagnostics or warnings'
    text = record.get('stdout_inline')
    if text is None and record.get('stdout_sha256') is None:
        return '', None  # the machine records no stdout for a silent program
    if not isinstance(text, str):
        return None, 'checked record has no inline stdout'
    if hashlib.sha256(text.encode()).hexdigest() != record.get('stdout_sha256'):
        return None, 'checked stdout digest differs from its record'
    return text, None


def lupin(args, row, out, want):
    d, entry = source(row)
    if row not in IN_PACKAGE:
        d = scratch(out, row, 'lupin')
        shutil.copy(HERE / row / 'main.lu', d / 'main.lu')
    env = dict(os.environ, LUPIN_STD=args.std)
    p = run([args.lupin, 'run', entry], d, args.bound, env)
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


def transcript_rows(path):
    rows = {}
    current = None
    for raw in Path(path).read_text(errors='replace').replace('\r', '').splitlines():
        if raw.startswith('PAX: '):
            continue
        cut = raw.find('user: ')
        line = raw if cut < 0 else raw[:cut]
        if cut == 0 or not line:
            continue
        if line.startswith('ROW '):
            current = line[4:].strip()
            rows[current] = {'lines': [], 'rc': None}
        elif line.startswith('END ') and current is not None:
            parts = line.split()
            rows[current]['rc'] = parts[2] if len(parts) > 2 else 'rc=?'
            current = None
        elif current is not None:
            rows[current]['lines'].append(line)
    return rows


def judge_transcript(args, table):
    rows = transcript_rows(args.transcript)
    failed = total = 0
    for row in args.rows.split(','):
        total += 1
        want = expected(table, row, 'native', args.host)
        got = rows.get(row)
        why = None
        if want is None:
            why = 'no expectation for host %s' % args.host
        elif got is None:
            why = 'not in the transcript'
        elif got['rc'] != 'rc=0':
            why = 'ended %s: %r' % (got['rc'], got['lines'][-6:])
        else:
            keys = {w.split('=', 1)[0] for w in want}
            kept = [l for l in got['lines'] if l.split('=', 1)[0] in keys]
            for l in got['lines']:
                if l not in kept:
                    print('  | %s' % l)
            why = compare('\n'.join(kept), want)
        if why:
            failed += 1
            print('FAIL deps %s native-%s: %s' % (row, args.host, why), flush=True)
        else:
            print('PASS deps %s native-%s' % (row, args.host), flush=True)
            for line in want:
                print('  %s' % line)
    print('DEPS rows=%d failed=%d host=%s transcript=%s' % (total, failed, args.host, args.transcript))
    return 1 if failed else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--wolf')
    parser.add_argument('--lupin')
    parser.add_argument('--std')
    parser.add_argument('--transcript', help='judge a console transcript instead of running')
    parser.add_argument('--host', default='darwin' if platform.system() == 'Darwin' else 'linux')
    parser.add_argument('--tiers', default='native,checked,lupin')
    parser.add_argument('--rows', default=','.join(ROWS))
    parser.add_argument('--out', type=Path, default=ROOT / 'target' / 'deps')
    parser.add_argument('--bound', type=int, default=120, help='seconds per run')
    parser.add_argument('--build-only', action='store_true', help='build native binaries, run nothing')
    args = parser.parse_args()
    table = expectations()
    if args.transcript:
        return judge_transcript(args, table)
    if not args.wolf or not args.std:
        parser.error('--wolf and --std are required unless --transcript is given')
    args.out.mkdir(parents=True, exist_ok=True)
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
