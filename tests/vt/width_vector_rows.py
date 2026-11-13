#!/usr/bin/env python3
"""Check the real native scalar-width function at every Unicode code point."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
LIMIT = 0x110000


def expected_vector():
    metadata = json.loads((ROOT / 'tests/vt/width-ranges.json').read_text())
    code = (ROOT / 'src/vt/width.lu').read_bytes()
    assert hashlib.sha256(code).hexdigest() == metadata['generated_sha256']
    result = bytearray([1]) * LIMIT
    for low, high, value in metadata['ranges']:
        assert 0 <= low <= high < LIMIT and value in (0, 2)
        result[low:high + 1] = bytes([value]) * (high - low + 1)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('program')
    args = parser.parse_args()
    result = subprocess.run([args.program], cwd=ROOT, capture_output=True, timeout=120)
    assert result.returncode == 0, (result.returncode, result.stderr[:1000])
    assert len(result.stdout) == LIMIT, ('native-width-vector-size', len(result.stdout), LIMIT)
    expected = expected_vector()
    if result.stdout != expected:
        cp = next(cp for cp, (got, want) in enumerate(zip(result.stdout, expected)) if got != want)
        raise AssertionError('native-width-vector U+%04X expected=%d got=%d' % (cp, expected[cp], result.stdout[cp]))
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_bytes(result.stdout)
    print('PASS native-width-vector code-points=%d sha256=%s' %
          (LIMIT, hashlib.sha256(result.stdout).hexdigest()))


if __name__ == '__main__':
    main()
