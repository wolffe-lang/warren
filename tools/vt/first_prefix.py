#!/usr/bin/env python3
"""Find the shortest observable byte prefix whose screen dumps differ.

Observers are JSON argv arrays (no shell). A literal {input} is replaced by
the candidate file; stdin also receives its bytes. A binary-search hint is
followed by exhaustive verification of earlier prefixes: terminal resets
can make divergence nonmonotone. Observer errors are errors, never matches.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen


class ObserverError(Exception):
    pass


def command(text):
    value = json.loads(text)
    if not isinstance(value, list) or not value or not all(isinstance(part, str) for part in value):
        raise ValueError('observer command must be a nonempty JSON string array')
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--left', type=command, required=True)
    parser.add_argument('--right', type=command, required=True)
    parser.add_argument('--max-bytes', type=int, default=4096)
    parser.add_argument('--timeout', type=float, default=60)
    args = parser.parse_args()
    if args.max_bytes < 0 or args.timeout <= 0:
        parser.error('bounds must be nonnegative and timeout positive')
    try:
        if args.input.stat().st_size > args.max_bytes:
            parser.error('input exceeds --max-bytes; no truncation was performed')
        raw = args.input.read_bytes()
        args.out.mkdir(parents=True, exist_ok=False)
    except OSError as error:
        parser.error('input/output setup failed: ' + str(error))
    candidate = (args.out / 'candidate.in').resolve()
    cache = {}
    best = len(raw) + 1
    evaluations = []

    def observe(words, data):
        argv = [part.replace('{input}', str(candidate)) for part in words]
        try:
            result = subprocess.run(argv, cwd=ROOT, input=data, capture_output=True, timeout=args.timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ObserverError('observer could not finish: ' + str(error)) from error
        if result.returncode:
            raise ObserverError('observer exit=%d stderr=%r' % (result.returncode, result.stderr[:2000]))
        try:
            got = screen.loads(result.stdout.decode('utf-8'))
        except (UnicodeError, ValueError, KeyError, IndexError) as error:
            raise ObserverError('observer did not produce format 1: ' + str(error)) from error
        return result.stdout, got

    def equal(length):
        nonlocal best
        if length in cache:
            return cache[length]
        data = raw[:length]
        candidate.write_bytes(data)
        left_bytes, left = observe(args.left, data)
        right_bytes, right = observe(args.right, data)
        differences = screen.compare(right, left)
        same = not differences
        cache[length] = same
        evaluations.append({'bytes': length, 'equal': same})
        if not same and length < best:
            best = length
            (args.out / 'first.in').write_bytes(data)
            (args.out / 'left.screen').write_bytes(left_bytes)
            (args.out / 'right.screen').write_bytes(right_bytes)
            (args.out / 'differences.json').write_text(json.dumps(differences, indent=2) + '\n')
        return same

    try:
        upper = len(raw)
        if not equal(upper):
            lower = 0
            while lower < upper:
                middle = (lower + upper) // 2
                if equal(middle):
                    lower = middle + 1
                else:
                    upper = middle
        # Final equality is not evidence that every earlier prefix matched.
        # Nor does bisection prove minimality when later controls erase damage.
        first = None
        for length in range(upper + 1):
            if not equal(length):
                first = length
                break
        verified = all(cache.get(length) is True for length in range(first or 0))
        result = {'schema': 1, 'input_sha256': hashlib.sha256(raw).hexdigest(),
                  'input_bytes': len(raw), 'shortest_prefix': first,
                  'earlier_prefixes_verified': verified, 'evaluations': evaluations,
                  'left': args.left, 'right': args.right}
        (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print('PREFIX shortest=%s input-bytes=%d evaluations=%d earlier-verified=%s' %
              (first, len(raw), len(cache), verified))
        return 1 if first is not None else 0
    except ObserverError as error:
        (args.out / 'observer-error.json').write_text(json.dumps({'error': str(error), 'evaluations': evaluations}, indent=2) + '\n')
        print('FAIL prefix-observer ' + str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
