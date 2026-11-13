#!/usr/bin/env python3
"""Compare the compiled/interpreted version answer to the canonical manifest."""
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def main():
    assert len(sys.argv) > 1, 'supply the answer-test command'
    manifest = (ROOT / 'src/wolf.pkg').read_text()
    versions = re.findall(r'\bversion\s*:\s*"([^"]+)"', manifest)
    assert len(versions) == 1
    expected = b'\x1bP>|warren ' + versions[0].encode('ascii') + b'\x1b\\'
    result = subprocess.run(sys.argv[1:], cwd=ROOT, capture_output=True, timeout=180)
    if result.returncode:
        sys.stdout.buffer.write(result.stdout)
        sys.stderr.buffer.write(result.stderr)
        raise SystemExit(result.returncode)
    lines = [line.removeprefix(b'VERSION-ANSWER ') for line in result.stdout.splitlines()
             if line.startswith(b'VERSION-ANSWER ')]
    assert lines == [expected.hex().encode('ascii')], 'version-answer-manifest-mismatch'
    print('PASS version-answer package-manifest byte-for-byte')


if __name__ == '__main__':
    main()
