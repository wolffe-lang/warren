#!/usr/bin/env python3
"""Compare three current grid cases, every format-1 field and cell.

D7 is explicit: these inputs never set 2026; warren must report it reset,
whereas the pinned reference reports unknown. No other field is rewritten.
"""
import copy
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen  # noqa: E402
sys.path.insert(0, str(ROOT / 'tests/vt'))
import cases  # noqa: E402


def main():
    names = {'sgr', 'erase', 'pending-wrap'}
    for name in names:
        assert (ROOT / ('tests/vt/grid-streams/' + name + '.in')).read_bytes() == cases.CASES[name]
        assert b'?2026' not in cases.CASES[name]
    done = subprocess.run(sys.argv[1:], cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert done.returncode == 0, done.stderr
    captured, current, lines = {}, None, []
    for line in done.stdout.splitlines():
        if line.startswith('BEGIN '):
            assert current is None
            current, lines = line[6:], []
        elif line.startswith('END '):
            assert current == line[4:] and current not in captured
            captured[current] = screen.loads('\n'.join(lines) + '\n')
            current = None
        else:
            assert current is not None
            lines.append(line)
    assert current is None and set(captured) == names
    failed = 0
    for name in sorted(names):
        expected = screen.loads((ROOT / ('tests/vt/expected/' + name + '.screen')).read_text())
        assert expected['modes']['synchronized-output'] == '?'
        ruled = copy.deepcopy(expected)
        ruled['modes']['synchronized-output'] = 0
        got = captured[name]
        assert screen.loads(screen.dumps(got)) == got
        differences = screen.compare(ruled, got)
        for row, detail in differences:
            print('FAIL grid-oracle-%s %s: %s' % (name, row, detail))
        if not differences:
            print('PASS grid-oracle-%s whole-screen D7=stored-reset' % name)
        failed += bool(differences)
    return 1 if failed else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AssertionError, ValueError, KeyError, OSError, subprocess.TimeoutExpired) as error:
        print('FAIL grid-oracle-cases ' + str(error))
        sys.exit(1)
