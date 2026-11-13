#!/usr/bin/env python3
"""Compare every field/cell of the eight committed reference cases.

Only D7 is adjusted: none of these streams sets 2026, so its written stored
state is reset rather than the reference's unknown. No other rewriting.
"""
import copy
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
import cases


def main():
    assert len(sys.argv) > 1
    output = ROOT / 'target/vt-case-comparison'
    output.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, data in sorted(cases.CASES.items()):
        assert b'2026' not in data
        expected = screen.loads((ROOT / 'tests/vt/expected' / (name + '.screen')).read_text())
        assert expected['modes']['synchronized-output'] == '?'
        ruled = copy.deepcopy(expected)
        ruled['modes']['synchronized-output'] = 0
        command = sys.argv[1:] + ['vt-dump', '--history-bytes', '65536']
        result = subprocess.run(command, cwd=ROOT, input=data, capture_output=True, timeout=180)
        assert result.returncode == 0, (name, result.returncode, result.stderr[:2000])
        assert not result.stderr, (name, result.stderr)
        (output / (name + '.actual.screen')).write_bytes(result.stdout)
        got = screen.loads(result.stdout.decode())
        differences = screen.compare(ruled, got)
        for row, detail in differences:
            print('FAIL vt-case-%s %s: %s' % (name, row, detail))
        if not differences:
            print('PASS vt-case-%s whole-screen D7=stored-reset' % name)
        failed += bool(differences)
    print('CASES total=%d failed=%d' % (len(cases.CASES), failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
