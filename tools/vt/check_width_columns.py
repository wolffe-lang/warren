#!/usr/bin/env python3
"""Current measured width columns: no D11 mismatches are allowed."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
from check_width_policy import exception_scalars, validate
from expectations import blank
import screen
BASE = ROOT / 'tests/vt/reference/width-columns-current'


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    assert manifest['schema'] == 1
    assert manifest['capture_head'] == 'c70c46ce8f675afb2d55ab86eaa27fa5545e056b'
    assert set(manifest['files']) == {'result.json', 'reference-pairs.json', 'sweep-result.json',
                                      'US.native.screen', 'GB.native.screen'}
    for name, wanted in manifest['files'].items():
        path = BASE / name
        assert path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576
        for _ in range(2):
            assert hashlib.sha256(path.read_bytes()).hexdigest() == wanted
    assert {p.name for p in BASE.iterdir()} == set(manifest['files']) | {'manifest.json'}
    result = json.loads((BASE / 'result.json').read_text())
    sweep = json.loads((BASE / 'sweep-result.json').read_text())
    validate(sweep)
    assert result['libc_version'] == '2.39' and result['locale'] == 'C.UTF-8'
    assert result['std_commit'] == '77cf3210a82c93dc05ded987c249bb69e79b0a89'
    assert result['std_function'] is None and result['std_status'] == 'unavailable at this pin'
    assert result['native_warren_head'] == manifest['capture_head']
    assert result['native_vector_sha256'] == sweep['native_vector_sha256']
    assert result['oracle_pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    expected = exception_scalars()
    assert len(result['scalars']) == len(expected) == 350
    for row, entry in zip(result['scalars'], expected):
        assert row['scalar'] == entry['scalar']
        assert row['std'] == 'unavailable at this pin'
        assert row['warren'] == row['libc_wcwidth'] == row['reference'] == entry['expected']
    raw_pairs = json.loads((BASE / 'reference-pairs.json').read_text())
    assert set(result['pairs']) == set(raw_pairs) == {'US', 'GB'}
    for name, points in {'US': (0x1F1FA, 0x1F1F8), 'GB': (0x1F1EC, 0x1F1E7)}.items():
        pair = result['pairs'][name]
        assert pair['reference'] == raw_pairs[name]
        assert pair['warren_actual_advance'] == pair['libc_wcswidth'] == pair['reference']['advance'] == 2
        assert pair['reference'] == {'reply_hex': '1b5b313b3452', 'row': 1, 'col': 4, 'advance': 2}
        model = blank(12, 4)
        model['title'] = ''
        model['cursor']['col'] = 4
        model['extents'][0] = 3
        model['rows'][0][:3] = [[1, 'U+0061', '-']] + [[1, 'U+%04X' % cp, '-'] for cp in points]
        actual = screen.loads((BASE / (name + '.native.screen')).read_text())
        assert not screen.compare(model, actual), screen.compare(model, actual)
    return manifest


if __name__ == '__main__':
    check()
    print('PASS current-width-measurements exhaustive-zero-differences350-exceptions-agree pairs-native-libc-reference=2 hashes-twice')
