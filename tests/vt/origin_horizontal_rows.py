#!/usr/bin/env python3
"""Absolute horizontal moves re-enter origin bounds after an above-region restore.

Compare complete screens with the live pinned binary reference. The existing
D12 guard handles unsigned relative CPR above the region; D7 sets only the
unreportable synchronized-output mode to its written reset value.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle
import screen
from origin_fixture import dump

CSI = b'\x1b['
# Set the title explicitly: the oracle's startup process title is not input state.
SETUP = b'\x1b]2;origin-horizontal\x1b\\' + CSI + b'?6h' + CSI + b'1;1H\x1b7' + CSI + b'4;7r\x1b8'
CASES = {
    'restored-above-region': (b'', 1, 1),
    'print-above-region': (b'xyz', 1, 4),
    'relative-forward-above-region': (CSI + b'5C', 1, 6),
    # Unlike CUF, the oracle's ANSI HPR also re-enters the region.
    'hpr-reenters-origin-region': (CSI + b'5a', 4, 6),
    'cha-reenters-origin-region': (CSI + b'7G', 4, 7),
    'hpa-reenters-origin-region': (CSI + b'9`', 4, 9),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('vt-dump command required')
    base = ROOT / 'target/origin-horizontal'
    base.mkdir(parents=True, exist_ok=True)
    failed = 0
    with oracle.Display() as display:
        for name, (suffix, row, col) in CASES.items():
            work = base / name
            work.mkdir(parents=True, exist_ok=True)
            data = SETUP + suffix
            source = work / 'input.in'
            source.write_bytes(data)
            expected = dump(display, source.resolve(), 12, 8, work.resolve())
            assert expected['region'] == [4, 7]
            assert expected['modes']['origin'] == 1
            assert (expected['cursor']['row'], expected['cursor']['col']) == (row, col), (name, expected['cursor'])
            assert expected['modes']['synchronized-output'] == '?'
            expected['modes']['synchronized-output'] = 0  # D7; no 2026 in these inputs.
            (work / 'reference.json').write_text(json.dumps(expected, indent=2) + '\n')
            result = subprocess.run(args.command + ['vt-dump', '--cols', '12', '--rows', '8', '--history-bytes', '1024'],
                                    input=data, capture_output=True, cwd=ROOT, timeout=180)
            (work / 'actual.screen').write_bytes(result.stdout)
            if result.returncode or result.stderr:
                print('FAIL origin-horizontal-%s candidate-exit=%d stderr=%r' % (name, result.returncode, result.stderr[:400]), flush=True)
                failed += 1
                continue
            actual = screen.loads(result.stdout.decode())
            differences = screen.compare(expected, actual)
            for kind, detail in differences:
                print('FAIL origin-horizontal-%s %s %s' % (name, kind, detail), flush=True)
            if differences:
                failed += 1
            else:
                print('PASS origin-horizontal-%s whole-screen D7/D12 cursor=%d;%d' % (name, row, col), flush=True)
    print('ORIGIN-HORIZONTAL cases=%d failed=%d' % (len(CASES), failed), flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
