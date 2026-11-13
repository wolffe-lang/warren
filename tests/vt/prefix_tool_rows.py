#!/usr/bin/env python3
"""Prove shortest-prefix search across divergence/convergence and observer errors."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / 'tools/vt/first_prefix.py'
OBSERVER = [sys.executable, '-I', str(ROOT / 'tests/vt/prefix_observer.py')]


def main():
    work = ROOT / 'target/prefix-tool-rows'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temporary:
        directory = Path(temporary)
        source = directory / 'source.in'
        for count in (5, 6):
            source.write_bytes(b'abcdef'[:count])
            output = directory / ('found-%d' % count)
            command = [sys.executable, '-I', str(TOOL), str(source), '--out', str(output),
                       '--left', json.dumps(OBSERVER + ['--fault']), '--right', json.dumps(OBSERVER)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
            assert result.returncode == 1, result.stderr
            verdict = json.loads((output / 'result.json').read_text())
            assert verdict['shortest_prefix'] == 2 and verdict['earlier_prefixes_verified']
            assert (output / 'first.in').read_bytes() == b'ab'
        equal = directory / 'equal'
        command = [sys.executable, '-I', str(TOOL), str(source), '--out', str(equal),
                   '--left', json.dumps(OBSERVER), '--right', json.dumps(OBSERVER)]
        assert subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60).returncode == 0
        assert json.loads((equal / 'result.json').read_text())['shortest_prefix'] is None
        error = directory / 'error'
        command = [sys.executable, '-I', str(TOOL), str(source), '--out', str(error),
                   '--left', json.dumps(OBSERVER + ['--error']), '--right', json.dumps(OBSERVER)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
        assert result.returncode == 2 and b'observer' in result.stderr
    print('PASS first-prefix shortest nonmonotone final-equal final-different observer-error')


if __name__ == '__main__':
    main()
