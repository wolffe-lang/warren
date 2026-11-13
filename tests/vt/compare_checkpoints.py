#!/usr/bin/env python3
"""Strict complete-frame comparisons at captured ASCII/colour/resize points."""
import argparse
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
from expectations import expected
from checkpoint_expectations import written_checkpoint


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('vt-dump program required')
    manifest = runpy.run_path(str(ROOT / 'tools/vt/check_checkpoints.py'))['check']()
    base = ROOT / 'tests/vt/reference/checkpoints'
    failed = limited = 0
    for name, entry in manifest['cases'].items():
        data = (base / entry['input_path']).read_bytes()
        command = args.command + ['vt-dump', '--history-bytes', '65536']
        if data.startswith(b'warren-rec 1\n'):
            command += ['--replay']
        else:
            cols, rows = entry['size']
            command += ['--cols', str(cols), '--rows', str(rows)]
        result = subprocess.run(command, cwd=ROOT, input=data, capture_output=True, timeout=180)
        assert result.returncode == 0 and not result.stderr, (name, result.returncode, result.stderr[:1000])
        raw = screen.loads((base / name / 'got.screen').read_text())
        _, written = expected('checkpoints', name, data, raw)
        limitations, written = written_checkpoint(name, data, written)
        differences = screen.compare(written, screen.loads(result.stdout.decode()))
        failed += bool(differences)
        for kind, detail in differences[:10]:
            print('FAIL checkpoint %s %s %s' % (name, kind, detail), flush=True)
        if not differences:
            if limitations:
                limited += 1
                print('LIMITED checkpoint %s reference report cannot express this: %s; complete source-bounded written frame holds' %
                      (name, ','.join(limitations)), flush=True)
            else:
                print('PASS checkpoint %s strict whole-screen D7' % name, flush=True)
    print('CHECKPOINTS cases=%d strict=%d limited=%d failed=%d' %
          (len(manifest['cases']), len(manifest['cases']) - limited - failed, limited, failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
