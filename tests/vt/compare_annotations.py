#!/usr/bin/env python3
"""Compare complete frames for FFF9..FFFB with measured reference omissions."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from check_annotations import check, screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    failed = 0
    for name, data, expected in check():
        done = subprocess.run(args.command + ['vt-dump', '--cols', '12', '--rows', '4', '--history-bytes', '0'],
                              input=data, capture_output=True, cwd=ROOT, timeout=180)
        differences = [('exit', str(done.returncode))] if done.returncode or done.stderr else screen.compare(expected, screen.loads(done.stdout.decode()))
        failed += bool(differences)
        print('%s annotation-complete-frame %s %s' % ('FAIL' if differences else 'PASS', name, differences or 'reference-agreement'), flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
