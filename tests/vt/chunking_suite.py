#!/usr/bin/env python3
"""P2 over the complete frozen corpus, preserving every recording resize.

An output record is one feed boundary in vt-dump replay. Rewriting output
records therefore tests actual bytewise and seeded random feed boundaries,
without relying on operating-system pipe read sizes or new CLI options.
"""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import random
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
from reference_inputs import fixture_input, inputs

MAGIC = b'warren-rec 1\n'


def events(data, replay):
    if not replay:
        return [('size', (80, 24)), ('o', data)]
    source = BytesIO(data)
    if source.readline() != MAGIC:
        raise ValueError('bad fixture recording magic')
    result = []
    while line := source.readline():
        fields = line.split()
        if fields[0] in (b'o', b'i') and len(fields) == 2:
            size = int(fields[1])
            if size < 0:
                raise ValueError('negative fixture payload')
            payload = source.read(size)
            if len(payload) != size or source.read(1) != b'\n':
                raise ValueError('truncated fixture payload')
            result.append((fields[0].decode(), payload))
        elif fields[0] in (b'size', b'r') and len(fields) == 3:
            result.append((fields[0].decode(), (int(fields[1]), int(fields[2]))))
        else:
            raise ValueError('bad fixture header')
    if not result or result[0][0] != 'size':
        raise ValueError('missing fixture initial size')
    return result


def encode(stream, strategy):
    output = BytesIO()
    output.write(MAGIC)
    rng = random.Random(0x575231)
    for kind, value in stream:
        if kind in ('size', 'r'):
            output.write(b'%s %d %d\n' % (kind.encode(), *value))
        elif kind == 'i':
            output.write(b'i %d\n' % len(value) + value + b'\n')
        elif kind == 'o':
            at = 0
            if not value:
                output.write(b'o 0\n\n')
            while at < len(value):
                length = 1 if strategy == 'bytewise' else rng.randint(1, 257) if strategy == 'random' else len(value)
                chunk = value[at:at + length]
                output.write(b'o %d\n' % len(chunk) + chunk + b'\n')
                at += len(chunk)
        else:
            raise ValueError('unknown fixture event')
    return output.getvalue()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=['all', 'census', 'recordings', 'fuzz-baseline'], default='all')
    parser.add_argument('--name')
    parser.add_argument('--out', type=Path, default=ROOT / 'target/vt-chunking')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('vt-dump program command required')
    args.out.mkdir(parents=True, exist_ok=True)
    total = failed = 0
    evidence = []
    for suite, streams in inputs().items():
        if args.suite not in ('all', suite):
            continue
        for name, (data, replay) in sorted(streams.items()):
            if args.name and args.name != name:
                continue
            data = fixture_input(suite, data)
            stream = events(data, replay)
            command = args.command + ['vt-dump', '--history-bytes', '65536']
            if replay:
                command += ['--replay']
            baseline = subprocess.run(command, cwd=ROOT, input=data, capture_output=True, timeout=180)
            if baseline.returncode:
                raise RuntimeError('baseline observer exit=%d: %r' % (baseline.returncode, baseline.stderr[:1000]))
            faults = []
            entry = {'suite': suite, 'name': name, 'input_sha256': hashlib.sha256(data).hexdigest(),
                     'screen_sha256': hashlib.sha256(baseline.stdout).hexdigest(), 'strategies': {}}
            for strategy in ('bytewise', 'random'):
                rewritten = encode(stream, strategy)
                got = subprocess.run(args.command + ['vt-dump', '--history-bytes', '65536', '--replay'],
                                     cwd=ROOT, input=rewritten, capture_output=True, timeout=180)
                same = got.returncode == 0 and got.stdout == baseline.stdout
                entry['strategies'][strategy] = {'equal': same, 'exit': got.returncode,
                                                'input_sha256': hashlib.sha256(rewritten).hexdigest()}
                if not same:
                    faults.append(strategy)
                    where = args.out / suite / name
                    where.mkdir(parents=True, exist_ok=True)
                    (where / 'baseline.screen').write_bytes(baseline.stdout)
                    (where / (strategy + '.screen')).write_bytes(got.stdout)
                    (where / (strategy + '.stderr')).write_bytes(got.stderr)
                    (where / (strategy + '.rec')).write_bytes(rewritten)
            evidence.append(entry)
            total += 1
            failed += bool(faults)
            print('%s chunking %s/%s bytewise random%s' %
                  ('FAIL' if faults else 'PASS', suite, name, ' faults=' + ','.join(faults) if faults else ''), flush=True)
    if not total:
        parser.error('selection contains no streams')
    (args.out / 'result.json').write_text(json.dumps({'schema': 1, 'streams': evidence, 'failed': failed}, indent=2) + '\n')
    print('CHUNKING streams=%d strategies=2 failed=%d' % (total, failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
