"""Deterministic owned inputs for frozen reference suites (data, not an oracle)."""
from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
import census
sys.path.insert(0, str(ROOT / 'tools/corpus'))
import fuzz


def recording(data, sizes):
    return (b'warren-rec 1\nsize 80 24\no %d\n' % len(data) + data + b'\n' +
            b''.join(b'r %d %d\n' % size for size in sizes))


def fixture_input(suite, data):
    if suite != 'recordings':
        return data
    setup = json.loads((ROOT / 'tests/vt/recording_setup.json').read_text())['recordings']
    prefix = bytes.fromhex(setup['startup_output_hex'])
    assert prefix == b'\x1b]2;' + setup['initial_title_utf8'].encode('utf-8') + b'\x07'
    magic = b'warren-rec 1\n'
    assert data.startswith(magic) and data[len(magic):].startswith(b'size ')
    at = data.index(b'\n', len(magic)) + 1
    return data[:at] + b'o %d\n' % len(prefix) + prefix + b'\n' + data[at:]


def inputs():
    return {
        'census': {name: (recording(data, sizes) if sizes else data, bool(sizes))
                   for name, (data, sizes) in census.CASES.items()},
        'recordings': {path.stem: (path.read_bytes(), True)
                       for path in sorted((ROOT / 'tests/corpus').glob('*.rec'))},
        'fuzz-baseline': {'fuzz-%04d' % seed: (fuzz.stream(seed, 2048), False)
                          for seed in range(1, 33)},
    }
