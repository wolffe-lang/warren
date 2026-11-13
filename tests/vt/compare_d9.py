#!/usr/bin/env python3
"""Compare original and repaired native replays with independent complete frames."""
import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import screen
from compare_suite import observe
from d9_fixture import definitions
from expectations import expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    runpy.run_path(str(ROOT / 'tools/vt/check_d9.py'))['check']()
    failures = 0
    out = ROOT / 'target/vt-d9-comparison'
    out.mkdir(parents=True, exist_ok=True)
    for name, definition in definitions().items():
        if definition['kind'] == 'complex-repaired':
            original = screen.loads((ROOT / 'tests/vt/reference/fuzz-baseline' / (name + '.screen')).read_text())
            labels, written = expected('fuzz-baseline', name, definition['original'], original)
        else:
            written = definition['written']
            labels = ['D9'] if definition['kind'] == 'minimal-repaired' else []
        observed = []
        for version, field in (('original', 'original'), ('repaired', 'input')):
            cols, rows = definition['size']
            command = args.command + ['vt-dump', '--cols', str(cols), '--rows', str(rows), '--history-bytes', '65536']
            got = observe(command, definition[field], 180, name + '/' + version)
            assert got.returncode == 0 and not got.stderr, (name, version, got.returncode, got.stderr)
            (out / (name + '.' + version + '.screen')).write_bytes(got.stdout)
            frame = screen.loads(got.stdout.decode())
            differences = screen.compare(written, frame)
            if differences:
                failures += 1
                print('FAIL d9-%s-%s %s' % (name, version, differences[:20]), flush=True)
            observed.append(frame)
        assert not screen.compare(*observed), ('native-original-versus-repaired', name)
        if not screen.compare(written, observed[0]):
            if any(label.startswith('RPT-') for label in labels):
                print('LIMITED d9-%s reference report cannot express column-one tab stop; source-witness frame checked' % name)
            print('PASS d9-%s original+repaired equal independent complete frame %s' % (name, ','.join(labels)), flush=True)
    print('D9-COMPARISON cases=37 replays=74 failed=%d' % failures)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
