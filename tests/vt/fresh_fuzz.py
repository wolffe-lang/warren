#!/usr/bin/env python3
"""Fresh reference/P2/R1/R3/R8 drive: 200 seeds per PR, 5000 nightly.

Any unexplained field stays red and is retained; no candidate output is a golden.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/corpus'))
import fuzz


def generated(count, size):
    if not 1 <= count <= 5000 or not 1 <= size <= 60000:
        raise ValueError('fresh drive requires 1..5000 seeds and 1..60000 requested bytes')
    return {'fresh-%04d' % seed: fuzz.stream(seed, size) for seed in range(1, count + 1)}


def profile_settings(name):
    profiles = json.loads((ROOT / 'tests/vt/fuzz-tiers.json').read_text())
    if name not in profiles:
        raise ValueError('unknown fresh fuzz profile')
    return profiles[name]['seeds'], profiles[name]['bytes']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('pull-request', 'nightly'), default='pull-request')
    parser.add_argument('--seeds', type=int)
    parser.add_argument('--bytes', type=int)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--deadline', type=float, default=3600)
    parser.add_argument('warren')
    parser.add_argument('properties')
    args = parser.parse_args()
    if not 0 < args.deadline <= 7200:
        parser.error('deadline must be positive and at most 7200 seconds')
    seeds, size = profile_settings(args.profile)
    if args.seeds is None:
        args.seeds = seeds
    if args.bytes is None:
        args.bytes = size
    selected = generated(args.seeds, args.bytes)
    sys.path.insert(0, str(ROOT / 'tools/oracle'))
    sys.path.insert(0, str(ROOT / 'tests/vt'))
    import run as oracle
    import screen
    from origin_fixture import dump as reference_dump
    from chunking_suite import events, encode as chunk_encode
    from corpus_properties import encode as property_encode, observe as property_observe
    sys.path.insert(0, str(ROOT / 'tools/vt'))
    from repair_background_fixture import repair
    from d9_fixture import background, with_background
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'seeds': args.seeds, 'requested_bytes': args.bytes,
                'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
                'cases': {}, 'failed': 0}
    started = time.monotonic()
    print('FRESH-DRIVE original-reference-dumps=%d repair-reference-dumps-at-most=%d terminal-passes-at-most=%d P2-strategies=2 resize-paths=4' % (args.seeds, args.seeds, 4 * args.seeds), flush=True)
    with oracle.Display() as display:
        for name, data in selected.items():
            if time.monotonic() - started > args.deadline:
                manifest['deadline_exhausted'] = True
                manifest['failed'] += 1
                break
            work = args.out / name
            work.mkdir()
            source = work / 'input.in'
            source.write_bytes(data)
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'failures': []}
            written = None
            repaired = None
            try:
                reference = reference_dump(display, source.resolve(), 80, 24, (work / 'reference').resolve())
                (work / 'reference.screen').write_text(screen.dumps(reference))
                entry['reference_report_divergences'] = ['D12'] if (work / 'reference/D12.json').exists() else []
                written = copy.deepcopy(reference)
                assert written['modes']['synchronized-output'] == '?'
                modes = re.findall(rb'\x1b\[\?2026([hl])', data)
                written['modes']['synchronized-output'] = int(bool(modes) and modes[-1] == b'h')
                (work / 'reference-plus-D7.screen').write_text(screen.dumps(written))
                repaired_input, injections = repair(data)
                entry['background_repair_injections'] = injections
                if injections:
                    fixed = work / 'background-repaired.in'
                    fixed.write_bytes(repaired_input)
                    repaired = reference_dump(display, fixed.resolve(), 80, 24, (work / 'repaired-reference').resolve())
                    (work / 'background-repaired-reference.screen').write_text(screen.dumps(repaired))
                    # Evidence, not an automatic D9 disposition: the original
                    # complete comparison below still fails on every difference.
                    delta = []
                    bounded = copy.deepcopy(reference)
                    for row in range(24):
                        for col in range(80):
                            old = background(reference['rows'][row][col][2])
                            new = background(repaired['rows'][row][col][2])
                            if old != new:
                                delta.append([row + 1, col + 1, old, new])
                                bounded['rows'][row][col][2] = with_background(bounded['rows'][row][col][2], new)
                    entry['reference_background_delta'] = delta
                    entry['repair_nonbackground_differences'] = screen.compare(bounded, repaired)
                    if entry['repair_nonbackground_differences']:
                        entry['failures'].append({'name': 'repair-outside-background-bound'})
            except (oracle.OracleError, ValueError, OSError, subprocess.TimeoutExpired) as error:
                entry['failures'].append({'name': 'reference-observation-or-repair', 'error': str(error)})
            command = [args.warren, 'vt-dump', '--history-bytes', '1048576']
            native = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=30)
            (work / 'native.stdout').write_bytes(native.stdout)
            (work / 'native.stderr').write_bytes(native.stderr)
            if native.returncode or native.stderr:
                entry['failures'].append({'name': 'native-exit', 'exit': native.returncode})
            else:
                actual = screen.loads(native.stdout.decode())
                if repaired is not None:
                    repaired['modes']['synchronized-output'] = 0
                    entry['native_versus_repaired_reference'] = screen.compare(repaired, actual)
                if written is not None:
                    differences = screen.compare(written, actual)
                    if differences:
                        entry['failures'].append({'name': 'unclassified-complete-frame', 'differences': differences})
                stream = events(data, False)
                for strategy in ('bytewise', 'random'):
                    chunked = subprocess.run(command + ['--replay'], input=chunk_encode(stream, strategy),
                                             capture_output=True, cwd=ROOT, timeout=30)
                    if chunked.returncode or chunked.stderr or chunked.stdout != native.stdout:
                        entry['failures'].append({'name': 'P2-' + strategy, 'exit': chunked.returncode})
                        (work / (strategy + '.stdout')).write_bytes(chunked.stdout)
                        (work / (strategy + '.stderr')).write_bytes(chunked.stderr)
                protocol, counts = property_encode(stream)
                result, frame = property_observe(args.properties, protocol, counts)
                if result.returncode or result.stderr or frame != native.stdout:
                    entry['failures'].append({'name': 'R1-R3-R8', 'exit': result.returncode})
                    (work / 'properties.stdout').write_bytes(result.stdout)
                    (work / 'properties.stderr').write_bytes(result.stderr)
            failed = bool(entry['failures'])
            manifest['failed'] += failed
            manifest['cases'][name] = entry
            print('%s fresh-fuzz %s bytes=%d failures=%s' %
                  ('FAIL' if failed else 'PASS', name, len(data), ','.join(row['name'] for row in entry['failures']) or '-'), flush=True)
            (args.out / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (args.out / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('FRESH-FUZZ completed=%d requested=%d failed=%d' % (len(manifest['cases']), args.seeds, manifest['failed']), flush=True)
    return bool(manifest['failed'])


if __name__ == '__main__':
    raise SystemExit(main())
