#!/usr/bin/env python3
"""Retain the measured zero-width cells, including strict report failures."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import run as oracle
import screen
from expectations import blank
BASE = ROOT / 'tests/vt/reference/zero-width'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    assert manifest['schema'] == 1 and manifest['terminal_process_budget'] == 56
    assert manifest['errors'] == []
    assert manifest['capture_head'] == 'c70c46ce8f675afb2d55ab86eaa27fa5545e056b'
    assert manifest['pins_sha256'] == digest(ROOT / 'warren-oracle.toml')
    captured = copy.deepcopy(manifest)
    for key in ('capture_head', 'pins_sha256', 'capture_manifest_sha256'):
        captured.pop(key)
    cases = runpy.run_path(str(ROOT / 'tests/vt/probes/zero_width_cells.py'))['cases']()
    assert set(manifest['cases']) == set(cases)
    seen = {'manifest.json'}
    complete = inconsistent = omitted = 0
    for name, (data, cp, context) in cases.items():
        entry = manifest['cases'][name]
        assert entry['input_sha256'] == hashlib.sha256(data).hexdigest()
        assert entry['scalar'] == 'U+%04X' % cp and entry['context'] == context
        assert (BASE / (name + '.in')).read_bytes() == data
        files = {name + '.in'} | {name + '/' + item for item in
            ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json')}
        if cp == 0xFFF9:
            files.add(name + '/got.screen')
        assert set(entry['files']) == files
        for relative, wanted in entry['files'].items():
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            path = BASE / relative
            assert path.is_file() and not path.is_symlink() and path.stat().st_size <= 1048576
            for _ in range(2):
                assert digest(path) == wanted
        seen.update(files)
        a = json.loads((BASE / name / 'A.json').read_text())
        s = json.loads((BASE / name / 'S.json').read_text())
        a['print'] = (BASE / name / 'A.print').read_bytes()
        s['print'] = (BASE / name / 'S.print').read_bytes()
        described = oracle.describe(a)
        if cp != 0xFFF9 and context in ('unwritten', 'first'):
            column = 5 if context == 'unwritten' else 1
            assert described['extents'] == [0, 0, 0, 0]
            assert a['print'] == b'\r\n' * 4
            assert oracle.parse_print(s['print'], 4)[0][column - 1][0] == [32, cp]
            try:
                oracle.finish(described, a, s)
            except oracle.OracleError as error:
                assert str(error) == 'row 1: unprinted cell %d is not blank' % column
            else:
                raise AssertionError(('inconsistent extent was accepted', name))
            inconsistent += 1
        else:
            got = oracle.finish(described, a, s)
            model = blank(12, 4)
            model['title'] = b'probe'.hex()
            mark = '' if cp == 0xFFF9 else '+U+%04X' % cp
            if context == 'ascii':
                model['cursor']['col'] = 2
                model['extents'][0] = 1
                model['rows'][0][0] = [1, 'U+0061' + mark, '-']
            elif context == 'wide':
                model['cursor']['col'] = 3
                model['extents'][0] = 2
                model['rows'][0][:2] = [[2, 'U+4E2D' + mark, '-'], [0, '-', '-']]
            elif context == 'unwritten':
                model['cursor']['col'] = 5
            got['modes']['synchronized-output'] = 0
            assert not screen.compare(model, got), (name, screen.compare(model, got))
            if cp == 0xFFF9:
                saved = screen.loads((BASE / name / 'got.screen').read_text())
                saved['modes']['synchronized-output'] = 0
                assert not screen.compare(saved, got)
                omitted += 1
            complete += 1
        captured['cases'][name].pop('files')
    assert complete == 16 and inconsistent == 12 and omitted == 4
    assert {str(path.relative_to(BASE)) for path in BASE.rglob('*') if path.is_file()} == seen
    assert hashlib.sha256((json.dumps(captured, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    return manifest


if __name__ == '__main__':
    check()
    print('PASS frozen-zero-width complete16 strict-inconsistencies12 FFF9-omitted4 hashes-twice no-candidate-expectations')
