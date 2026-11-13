#!/usr/bin/env python3
"""Native R1/R3/R8 over every owned corpus stream, with CLI-loader crosschecks."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
from chunking_suite import events
from reference_inputs import inputs, fixture_input


def encode(stream):
    assert stream and stream[0][0] == 'size'
    data = bytearray(b'WRP1' + struct.pack('<II', *stream[0][1]))
    fed = resizes = rolling = 0
    for kind, value in stream[1:]:
        if kind == 'o':
            data += b'\x01' + struct.pack('<I', len(value)) + value
            fed += len(value)
            for raw in value:
                rolling = (rolling * 257 + raw) % 2147483647
        elif kind == 'r':
            data += b'\x02' + struct.pack('<II', *value)
            resizes += 1
        else:
            assert kind == 'i'
    data += b'\0'
    assert len(data) <= 65536
    return bytes(data), (fed, resizes, rolling)


def observe(program, protocol, counts):
    result = subprocess.run([program], cwd=ROOT, input=protocol, capture_output=True, timeout=120)
    if result.returncode:
        return result, None
    begin, end = b'BASE-DUMP-BEGIN\n', b'BASE-DUMP-END\n'
    assert result.stdout.startswith(begin) and result.stdout.count(end) == 1
    frame, footer = result.stdout[len(begin):].split(end, 1)
    match = re.fullmatch(rb'CORPUS-PROPERTIES bytes=(\d+) resizes=(\d+) rolling=(\d+) pairs=4\n', footer)
    assert match and tuple(map(int, match.groups())) == counts, (counts, footer)
    return result, frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('all', 'census', 'recordings', 'fuzz-baseline'), default='all')
    parser.add_argument('--name')
    parser.add_argument('--out', type=Path, default=ROOT / 'target/corpus-properties')
    parser.add_argument('properties')
    parser.add_argument('warren')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    total = failed = 0
    evidence = []
    for suite, streams in inputs().items():
        if args.suite not in ('all', suite):
            continue
        for name, (source, replay) in sorted(streams.items()):
            if args.name and args.name != name:
                continue
            source = fixture_input(suite, source)
            protocol, counts = encode(events(source, replay))
            got, frame = observe(args.properties, protocol, counts)
            baseline = None
            if frame is not None:
                command = [args.warren, 'vt-dump', '--history-bytes', '1048576'] + (['--replay'] if replay else [])
                baseline = subprocess.run(command, cwd=ROOT, input=source, capture_output=True, timeout=30)
            good = got.returncode == 0 and not got.stderr and baseline is not None and baseline.returncode == 0 and not baseline.stderr and baseline.stdout == frame
            evidence.append({'suite': suite, 'name': name, 'input_sha256': hashlib.sha256(source).hexdigest(),
                             'fed_bytes': counts[0], 'input_resizes': counts[1], 'rolling': counts[2],
                             'exit': got.returncode, 'passed': good})
            if not good:
                where = args.out / suite / name
                where.mkdir(parents=True, exist_ok=True)
                (where / 'properties.stdout').write_bytes(got.stdout)
                (where / 'properties.stderr').write_bytes(got.stderr)
                (where / 'input.wrp').write_bytes(protocol)
                if baseline:
                    (where / 'cli.stdout').write_bytes(baseline.stdout)
                    (where / 'cli.stderr').write_bytes(baseline.stderr)
            total += 1
            failed += not good
            print('%s corpus-resize-properties %s/%s R1-content+rendition R3-four-paths R8 CLI-crosscheck exit=%d' %
                  ('PASS' if good else 'FAIL', suite, name, got.returncode), flush=True)
    assert total
    (args.out / 'result.json').write_text(json.dumps({'schema': 1, 'streams': evidence, 'failed': failed}, indent=2) + '\n')
    print('CORPUS-PROPERTIES streams=%d pairs=4 failed=%d' % (total, failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
