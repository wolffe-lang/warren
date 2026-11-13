#!/usr/bin/env python3
"""Compare focused probes, separating strict matches from report limitations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen
BASE = ROOT / 'tests/vt/reference/interactions'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('vt-dump program required')
    manifest = json.loads((BASE / 'index.json').read_text())
    probe = runpy.run_path(str(ROOT / 'tests/vt/probes/terminal_interactions.py'))
    assert set(manifest['cases']) == set(probe['CASES'])
    assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    strict = limited = failed = 0
    for name, entry in manifest['cases'].items():
        directory = BASE / name
        for filename, digest in entry['files'].items():
            for _ in range(2):
                assert hashlib.sha256((directory / filename).read_bytes()).hexdigest() == digest, (name, filename)
        data = (directory / 'input.in').read_bytes()
        assert data == probe['HEAD'] + probe['CASES'][name]
        result = subprocess.run(args.command + ['vt-dump', '--cols', '12', '--rows', '4', '--history-bytes', '1024'],
                                cwd=ROOT, input=data, capture_output=True, timeout=180)
        if result.returncode:
            print('FAIL focused-probe %s observer-exit=%d %r' % (name, result.returncode, result.stderr[:400]), flush=True)
            failed += 1
            continue
        got = screen.loads(result.stdout.decode())
        reference = screen.loads((directory / 'got.screen').read_text())
        reference['modes']['synchronized-output'] = 0  # D7, input contains no 2026.
        written = copy.deepcopy(reference)
        limitation = entry['limitation']
        if limitation == 'RPT-TABS-COLUMN-ONE':
            assert reference['tabs'] == []
            written['tabs'] = [1]  # HTS at the explicitly addressed initial cell.
        elif limitation == 'RPT-BRIGHT-BOLD-COLOUR':
            assert reference['rows'][0][0] == [1, 'U+0058', 'bold,fg=idx:1,bg=idx:2']
            written['rows'][0][0][2] = 'bold,fg=idx:9,bg=idx:2'  # Exact literal 91 / 38;5;9.
        elif limitation is not None:
            raise ValueError('unknown report limitation')
        differences = screen.compare(written, got)
        if differences:
            failed += 1
            for kind, detail in differences:
                print('FAIL focused-probe %s %s %s' % (name, kind, detail), flush=True)
        elif limitation:
            limited += 1
            print('LIMITED focused-probe %s reference report cannot express this: %s; written expectation holds' %
                  (name, limitation), flush=True)
        else:
            strict += 1
            print('PASS focused-probe %s strict whole-screen D7' % name, flush=True)
    print('FOCUSED-PROBES strict=%d limited=%d failed=%d' % (strict, limited, failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
