#!/usr/bin/env python3
"""warren's frames for D15's frozen inputs, never compared with the reference.

On a trigger case both the original and the split input must give warren's
written frame (tests/vt/d15_fixture.py): warren keeps the cell that moves in
from the last column. A control expects the reference's own frame.
"""
import argparse
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import screen  # noqa: E402
from compare_suite import observe  # noqa: E402
from d15_fixture import definitions  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    runpy.run_path(str(ROOT / 'tools/vt/check_d15.py'))['check']()
    out = ROOT / 'target/vt-d15-comparison'
    out.mkdir(parents=True, exist_ok=True)
    failures = replays = 0
    cases = definitions()
    for name, definition in cases.items():
        if definition['kind'] == 'trigger':
            written, label = definition['written'], 'written D15'
        else:
            written = screen.loads((ROOT / 'tests/vt/reference/d15' / name / 'original/got.screen').read_text())
            written['modes']['synchronized-output'] = 0
            label = 'reference D7'
        versions = [('original', 'original')] + ([('split', 'input')] if definition['kind'] == 'trigger' else [])
        failed = False
        for version, field in versions:
            cols, rows = definition['size']
            command = args.command + ['vt-dump', '--cols', str(cols), '--rows', str(rows), '--history-bytes', '65536']
            got = observe(command, definition[field], 180, name + '/' + version)
            assert got.returncode == 0 and not got.stderr, (name, version, got.returncode, got.stderr[:2000])
            (out / (name + '.' + version + '.screen')).write_bytes(got.stdout)
            differences = screen.compare(written, screen.loads(got.stdout.decode()))
            replays += 1
            if differences:
                failed = True
                print('FAIL d15-%s-%s %s' % (name, version, differences[:20]), flush=True)
        failures += failed
        if not failed:
            print('PASS d15-%s %s equal the %s frame' % (
                name, '+'.join(version for version, _ in versions), label), flush=True)
    print('D15-COMPARISON cases=%d replays=%d failed=%d' % (len(cases), replays, failures))
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
