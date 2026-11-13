#!/usr/bin/env python3
"""Verify raw D9 observations and independently constructed written frames."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'tests/vt/reference/inverse'
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
from inverse_expected import expected, ATTRIBUTES


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    generated = runpy.run_path(str(ROOT / 'tests/vt/probes/default_restoration.py'))['inverse_cases']()
    assert manifest['complete_dump_count'] == 12 and not manifest['errors']
    assert set(manifest['cases']) == set(generated) == set(ATTRIBUTES)
    assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    assert manifest['written_model_sha256'] == hashlib.sha256((ROOT / 'tests/vt/inverse_expected.py').read_bytes()).hexdigest()
    original = copy.deepcopy(manifest)
    for key in ('capture_head', 'capture_manifest_sha256', 'written_model_sha256'):
        original.pop(key)
    seen = {'manifest.json'}
    divergences = 0
    for name, (data, cols, rows) in generated.items():
        entry = manifest['cases'][name]
        assert entry['size'] == [cols, rows] and entry['input_path'] == name + '.in'
        assert (BASE / entry['input_path']).read_bytes() == data
        assert entry['input_sha256'] == hashlib.sha256(data).hexdigest()
        required = {name + '/' + file for file in ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json', 'got.screen', 'pen.json', 'written.screen')}
        required.add(entry['input_path'])
        assert set(entry['files']) == required
        assert entry['screen_sha256'] == entry['files'][name + '/got.screen']
        assert entry['written_sha256'] == entry['files'][name + '/written.screen']
        for relative, digest in entry['files'].items():
            file = BASE / relative
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            assert file.is_file() and not file.is_symlink() and file.stat().st_size <= 1048576
            for _ in range(2):
                assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, relative
        seen.update(required)
        assert json.loads((BASE / name / 'pen.json').read_text())['sgr_report_hex'] == entry['sgr_report_hex']
        written = screen.dumps(expected(name)).encode()
        assert (BASE / name / 'written.screen').read_bytes() == written
        assert hashlib.sha256(written).hexdigest() == entry['written_sha256']
        reference = screen.loads((BASE / name / 'got.screen').read_text())
        reference['modes']['synchronized-output'] = 0  # D7, no 2026 in these inputs.
        differences = screen.compare(expected(name), reference)
        if differences:
            assert len(differences) == 1 and differences[0][0] == 'cell-attribute' and 'bg=' in differences[0][1], (name, differences)
            divergences += 1
        for key in ('input_path', 'files', 'written_sha256'):
            original['cases'][name].pop(key)
    assert divergences == 8
    assert {str(file.relative_to(BASE)) for file in BASE.rglob('*') if file.is_file()} == seen
    assert hashlib.sha256((json.dumps(original, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    return manifest


if __name__ == '__main__':
    check()
    print('PASS inverse-reference cases=12 independent-written=12 D9-background-divergences=8 controls=4')
