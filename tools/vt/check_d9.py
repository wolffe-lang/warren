#!/usr/bin/env python3
"""Bind all repaired-reference D9 cells, original inputs and raw observations."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
sys.path.insert(0, str(ROOT / 'tools/oracle'))
from d9_fixture import definitions, complex_bound, verify_background_delta
import screen

BASE = ROOT / 'tests/vt/reference/d9'


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    generated = definitions()
    assert manifest['schema'] == 1
    assert manifest['complete_dump_count'] == 37 and manifest['pen_status_count'] == 22
    assert not manifest['errors'] and not manifest['mixed_background_disagreements']
    assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    assert manifest['tracer_sha256'] == hashlib.sha256((ROOT / 'tools/vt/repair_background_fixture.py').read_bytes()).hexdigest()
    assert set(manifest['cases']) == set(generated)
    captured = copy.deepcopy(manifest)
    captured.pop('capture_head')
    captured.pop('capture_manifest_sha256')
    seen = {'manifest.json'}
    for name, definition in generated.items():
        entry = manifest['cases'][name]
        assert entry['kind'] == definition['kind'] and entry['size'] == definition['size']
        assert entry['injections'] == definition['injections']
        for key, suffix in (('original', '.original.in'), ('input', '.in')):
            raw = (BASE / (name + suffix)).read_bytes()
            assert raw == definition[key]
            assert hashlib.sha256(raw).hexdigest() == entry[key + '_sha256']
        files = {name + suffix for suffix in ('.in', '.original.in')}
        files |= {name + '/' + part for part in ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json', 'got.screen')}
        if definition['pen_status']:
            files.add(name + '/pen.json')
        assert set(entry['files']) == files
        for relative, digest in entry['files'].items():
            path = BASE / relative
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 1048576
            for _ in range(2):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, relative
        assert entry['screen_sha256'] == entry['files'][name + '/got.screen']
        got = screen.loads((BASE / name / 'got.screen').read_text())
        if definition['kind'] == 'complex-repaired':
            raw = (ROOT / 'tests/vt/reference/fuzz-baseline' / (name + '.screen')).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == entry['original_screen_sha256']
            original = screen.loads(raw.decode())
            cells, value = complex_bound(name, original)
            assert entry['bound_cells'] == [list(cell) for cell in sorted(cells)]
            assert entry['bound_field'] == 'background' and entry['corrected_background'] == value
            verify_background_delta(original, got, cells, value)
        elif definition['kind'] == 'minimal-repaired':
            original = screen.loads((ROOT / 'tests/vt/reference/inverse' / definition['original_case'] / 'got.screen').read_text())
            cells = {tuple(cell) for cell in entry['bound_cells']}
            verify_background_delta(original, got, cells, entry['corrected_background'])
            got['modes']['synchronized-output'] = 0
            assert not screen.compare(definition['written'], got)
        elif definition['kind'] == 'mixed-background-measurement':
            got['modes']['synchronized-output'] = 0
            assert not screen.compare(definition['written'], got)
            assert entry['written_differences'] == []
        else:
            assert definition['kind'] == 'bright-report-measurement'
            # The complete literal written frame is deliberately distinct from
            # the raw printer report: blue12 under bold is printed as blue4.
            folded = copy.deepcopy(definition['written'])
            folded['rows'][0][0][2] = 'bold,fg=idx:4'
            got['modes']['synchronized-output'] = 0
            assert not screen.compare(folded, got)
            assert entry['written_differences']
        seen.update(files)
        captured['cases'][name].pop('files')
    assert {str(path.relative_to(BASE)) for path in BASE.rglob('*') if path.is_file()} == seen
    raw = (json.dumps(captured, indent=2) + '\n').encode()
    assert hashlib.sha256(raw).hexdigest() == manifest['capture_manifest_sha256']
    return manifest


if __name__ == '__main__':
    check()
    print('PASS frozen-d9 cases=37 original+repaired-inputs raw-replies+prints+screens hashes-twice exact-bg-cell-field-bounds mixed-background=20 blue-bold-report=2')
