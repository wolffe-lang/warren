"""Deterministic owned inputs for frozen reference suites (data, not an oracle)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
import census
sys.path.insert(0, str(ROOT / 'tools/corpus'))
import fuzz


def recording(data, sizes):
    return (b'warren-rec 1\nsize 80 24\no %d\n' % len(data) + data + b'\n' +
            b''.join(b'r %d %d\n' % size for size in sizes))


def inputs():
    return {
        'census': {name: (recording(data, sizes) if sizes else data, bool(sizes))
                   for name, (data, sizes) in census.CASES.items()},
        'recordings': {path.stem: (path.read_bytes(), True)
                       for path in sorted((ROOT / 'tests/corpus').glob('*.rec'))},
        'fuzz-baseline': {'fuzz-%04d' % seed: (fuzz.stream(seed, 2048), False)
                          for seed in range(1, 33)},
    }
