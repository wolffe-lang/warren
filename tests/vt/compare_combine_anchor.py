#!/usr/bin/env python3
"""Compare113 complete anchor frames; the one named RI report stays open."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from check_combine_anchor import check, screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    failed = 0
    for name, data, replay, cols, rows, expected, labels in check():
        command = args.command + ['vt-dump', '--history-bytes', '4096']
        command += ['--replay'] if replay else ['--cols', str(cols), '--rows', str(rows)]
        done = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=180)
        differences = [('exit', str(done.returncode))] if done.returncode or done.stderr else screen.compare(expected, screen.loads(done.stdout.decode()))
        failed += bool(differences)
        print('%s combine-anchor-frame %s %s %s' %
              ('FAIL' if differences else 'PASS', name, '+'.join(labels) or 'reference', differences[:8] or '-'), flush=True)
    print('COMBINE-ANCHOR-FRAMES comparable=113 failed=%d open-RI-question=1' % failed, flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
