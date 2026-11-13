#!/usr/bin/env python3
"""Actual native/frozen-reference ASCII witness for first_prefix.py.

This adapter only accepts prefixes of AZZ, all in parser ground. It is not a
claim that arbitrary incomplete terminal prefixes can be queried unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--native')
    group.add_argument('--reference', type=Path)
    args = parser.parse_args()
    data = sys.stdin.buffer.read(4)
    if len(data) > 3 or not b'AZZ'.startswith(data):
        parser.error('this reference witness accepts only prefixes of AZZ')
    setup = runpy.run_path(str(ROOT / 'tests/vt/probes/colour_and_checkpoints.py'))['HEAD']
    prepared = setup + data
    if args.native:
        result = subprocess.run([args.native, 'vt-dump', '--cols', '8', '--rows', '2', '--history-bytes', '1024'],
                                cwd=ROOT, input=prepared, capture_output=True, timeout=30)
        if result.returncode or result.stderr:
            print('FAIL native witness observer exit=%d stderr=%r' % (result.returncode, result.stderr[:200]), file=sys.stderr)
            return 2
        screen.loads(result.stdout.decode())
        sys.stdout.buffer.write(result.stdout)
    else:
        manifest = json.loads((args.reference / 'manifest.json').read_text())
        assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
        name = 'ascii-prefix-%d' % len(data)
        entry = manifest['cases'][name]
        assert entry['kind'] == 'ascii-prefix-witness' and entry['prefix_bytes'] == len(data)
        assert entry['input_sha256'] == hashlib.sha256(prepared).hexdigest()
        raw = (args.reference / name / 'got.screen').read_bytes()
        assert entry['screen_sha256'] == hashlib.sha256(raw).hexdigest()
        reference = screen.loads(raw.decode())
        assert reference['size'] == [8, 2] and reference['modes']['synchronized-output'] == '?'
        reference['modes']['synchronized-output'] = 0  # Named D7, no 2026 bytes in this fixture.
        sys.stdout.write(screen.dumps(reference))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
