#!/usr/bin/env python3
"""Compare frozen census/recording/baseline-fuzz data with named policies."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
from reference_inputs import inputs, fixture_input
from expectations import expected


def observe(command, data, timeout, label, interval=30):
    """Keep a finite observer deadline visible; never change interpreter caps."""
    if not math.isfinite(timeout) or timeout <= 0 or not math.isfinite(interval) or interval <= 0:
        raise ValueError('observer deadline and interval must be finite and positive')
    started = time.monotonic()
    deadline = started + timeout
    work = ROOT / 'target/observer-inputs'
    work.mkdir(parents=True, exist_ok=True)
    # communicate() retries do not resume an unfinished stdin PIPE write.
    # A seekable fixture descriptor preserves all bytes across heartbeats.
    with tempfile.TemporaryFile(dir=work) as source:
        source.write(data)
        source.seek(0)
        process = subprocess.Popen(command, cwd=ROOT, stdin=source, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            while True:
                remaining = deadline - time.monotonic()
                try:
                    output, errors = process.communicate(timeout=max(0.001, min(interval, remaining)))
                    return subprocess.CompletedProcess(command, process.returncode, output, errors)
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        process.kill()  # Only the observer PID created here.
                        output, errors = process.communicate()
                        raise subprocess.TimeoutExpired(command, timeout, output=output, stderr=errors)
                    print('WAIT observer %s elapsed-seconds=%d deadline-seconds=%g' %
                          (label, time.monotonic() - started, timeout), flush=True)
        except BaseException:
            if process.poll() is None:
                process.kill()
            process.communicate()
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('census', 'recordings', 'fuzz-baseline', 'all'), default='all')
    parser.add_argument('--name')
    parser.add_argument('--observer-timeout', type=float, default=180,
                        help='wall-clock deadline only; interpreter memory/step caps are unchanged')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not math.isfinite(args.observer_timeout) or args.observer_timeout <= 0:
        parser.error('observer timeout must be finite and positive')
    assert args.command
    index = json.loads((ROOT / 'tests/vt/reference/index.json').read_text())
    assert hashlib.sha256((ROOT / 'tests/vt/recording_setup.json').read_bytes()).hexdigest() == index['fixture_setup_sha256']
    sources = inputs()
    failures = 0
    count = 0
    for suite, entries in sources.items():
        if args.suite not in ('all', suite):
            continue
        output = ROOT / 'target/vt-comparison' / suite
        output.mkdir(parents=True, exist_ok=True)
        for name, (data, replay) in sorted(entries.items()):
            if args.name and name != args.name:
                continue
            binding = index['suites'][suite][name]
            assert hashlib.sha256(data).hexdigest() == binding['input_sha256']
            reference = (ROOT / 'tests/vt/reference' / suite / (name + '.screen')).read_bytes()
            assert hashlib.sha256(reference).hexdigest() == binding['screen_sha256']
            labels, ruled = expected(suite, name, data, screen.loads(reference.decode()))
            command = args.command + ['vt-dump', '--history-bytes', '65536'] + (['--replay'] if replay else [])
            if suite == 'recordings':
                labels.append('fixture-startup-title')
                unseeded = observe(command, data, args.observer_timeout, suite + '/' + name + '/unseeded')
                (output / (name + '.unseeded.stdout')).write_bytes(unseeded.stdout)
                (output / (name + '.unseeded.stderr')).write_bytes(unseeded.stderr)
                assert unseeded.returncode == 0 and not unseeded.stderr, (suite, name, unseeded.returncode, unseeded.stderr[:2000])
                unseeded_screen = screen.loads(unseeded.stdout.decode())
                unseeded_differences = screen.compare(ruled, unseeded_screen)
                assert len(unseeded_differences) == 1 and unseeded_differences[0][0] == 'title', (name, unseeded_differences[:20])
                assert unseeded_screen['title'] == ''
                print('PASS fixture-startup-title-%s unseeded-differs-only-title' % name, flush=True)
            prepared = fixture_input(suite, data)
            result = observe(command, prepared, args.observer_timeout, suite + '/' + name + '/prepared')
            (output / (name + '.observer.stderr')).write_bytes(result.stderr)
            if result.returncode:
                (output / (name + '.observer.stdout')).write_bytes(result.stdout)
            assert result.returncode == 0, (suite, name, result.returncode, result.stderr[:2000])
            assert not result.stderr, (suite, name, result.stderr)
            (output / (name + '.actual.screen')).write_bytes(result.stdout)
            (output / (name + '.expected.screen')).write_text(screen.dumps(ruled))
            got = screen.loads(result.stdout.decode())
            differences = screen.compare(ruled, got)
            for row, detail in differences[:20]:
                print('FAIL vt-%s-%s %s: %s' % (suite, name, row, detail), flush=True)
            if not differences:
                print('PASS vt-%s-%s whole-screen %s' % (suite, name, ','.join(labels)), flush=True)
            else:
                print('DIFFERENCES %s/%s total=%d' % (suite, name, len(differences)), flush=True)
            failures += bool(differences)
            count += 1
    assert count
    print('COMPARISON streams=%d failed=%d suite=%s' % (count, failures, args.suite))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
