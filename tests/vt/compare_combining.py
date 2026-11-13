#!/usr/bin/env python3
"""Complete combining frames: independent D10 expectations, two strict controls."""
import argparse
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import screen
from combining_cases import cases
from combining_expected import expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    manifest = runpy.run_path(str(ROOT / 'tools/vt/check_combining.py'))['check']()
    failures = 0
    for name, (data, cols, rows, _) in cases().items():
        replay = data.startswith(b'warren-rec 1\n')
        command = args.command + ['vt-dump', '--history-bytes', '4096']
        command += ['--replay'] if replay else ['--cols', str(cols), '--rows', str(rows)]
        got = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=180)
        assert got.returncode == 0 and not got.stderr, (name, got.returncode, got.stderr)
        if name in manifest['errors']:
            written = expected(name)
            print('LIMITED combining-%s D10 reference reports inconsistent written extent and full cells' % name, flush=True)
        else:
            written = screen.loads((ROOT / 'tests/vt/reference/combining' / name / 'got.screen').read_text())
            written['modes']['synchronized-output'] = 0
        differences = screen.compare(written, screen.loads(got.stdout.decode()))
        failures += bool(differences)
        print('%s combining-%s complete-frame %s' %
              ('FAIL' if differences else 'PASS', name, differences[:10] if differences else ('D10-independent-contract' if name in manifest['errors'] else 'REFERENCE+D7')), flush=True)
    print('COMBINING-COMPARISON cases=8 failed=%d' % failures)
    return bool(failures)


if __name__ == '__main__':
    raise SystemExit(main())
