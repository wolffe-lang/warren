#!/usr/bin/env python3
"""Owned tiny observable for first-prefix search; not a terminal oracle."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
from expectations import blank

if '--error' in sys.argv:
    raise SystemExit(7)
data = sys.stdin.buffer.read()
got = blank(8, 1)
if data:
    got['extents'][0] = 1
    fault = '--fault' in sys.argv and len(data) in (2, 4, 6)
    got['rows'][0][0] = [1, 'U+0042' if fault else 'U+0041', '-']
sys.stdout.write(screen.dumps(got))
