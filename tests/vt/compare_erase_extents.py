#!/usr/bin/env python3
"""Complete-frame D14 bounds; D6 resize frames use independent contracts."""
import argparse
from pathlib import Path
import subprocess
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from check_erase_extents import check, screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    failed = 0
    for name, data, replay, expected, labels in check():
        command = args.command + ['vt-dump', '--history-bytes', '4096']
        command += ['--replay'] if replay else ['--cols', '12', '--rows', '4']
        done = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=180)
        differences = [('exit', str(done.returncode))] if done.returncode or done.stderr else screen.compare(expected, screen.loads(done.stdout.decode()))
        failed += bool(differences)
        print('%s erase-extent-complete-frame %s %s %s' %
              ('FAIL' if differences else 'PASS', name, '+'.join(labels) or 'strict-reference', differences or '-'), flush=True)
    print('ERASE-EXTENT-COMPLETE frames=32 failed=%d' % failed, flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
