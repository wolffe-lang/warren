#!/usr/bin/env python3
"""Validate all12 observed annotation-control omissions as complete frames."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
sys.path.insert(0, str(ROOT / 'tools/vt'))
import run as oracle
import screen
from expectations import blank
from check_zero_width import check as check_zero_width
BASE = ROOT / 'tests/vt/reference/annotations'


def check():
    check_zero_width()
    manifest = json.loads((BASE / 'manifest.json').read_text())
    assert manifest['schema'] == 1 and manifest['errors'] == []
    assert manifest['terminal_process_budget'] == 16
    assert manifest['capture_head'] == 'efcb5fab96c2af4b64a6a559c5cdb1234fa78020'
    assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    sources = runpy.run_path(str(ROOT / 'tests/vt/probes/annotation_cells.py'))['cases']()
    assert set(sources) == set(manifest['cases'])
    captured = copy.deepcopy(manifest)
    for key in ('capture_head', 'pins_sha256', 'capture_manifest_sha256'):
        captured.pop(key)
    seen = {'manifest.json'}
    for name, (data, cp, context) in sources.items():
        entry = manifest['cases'][name]
        assert entry['input_sha256'] == hashlib.sha256(data).hexdigest()
        assert entry['scalar'] == 'U+%04X' % cp and entry['context'] == context
        assert entry['classification'] == 'complete-reference-frame'
        assert (BASE / (name + '.in')).read_bytes() == data
        files = {name + '.in'} | {name + '/' + part for part in
            ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json', 'got.screen')}
        assert set(entry['files']) == files
        for relative, wanted in entry['files'].items():
            path = BASE / relative
            assert '..' not in Path(relative).parts and not Path(relative).is_absolute()
            assert path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576
            for _ in range(2):
                assert hashlib.sha256(path.read_bytes()).hexdigest() == wanted
        seen.update(files)
        captured['cases'][name].pop('files')
    assert hashlib.sha256((json.dumps(captured, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    assert {str(path.relative_to(BASE)) for path in BASE.rglob('*') if path.is_file()} == seen
    result = []
    for base in (ROOT / 'tests/vt/reference/zero-width', BASE):
        records = json.loads((base / 'manifest.json').read_text())['cases']
        for name, entry in records.items():
            if entry['scalar'] not in ('U+FFF9', 'U+FFFA', 'U+FFFB'):
                continue
            a = json.loads((base / name / 'A.json').read_text())
            s = json.loads((base / name / 'S.json').read_text())
            a['print'] = (base / name / 'A.print').read_bytes()
            s['print'] = (base / name / 'S.print').read_bytes()
            frame = oracle.finish(oracle.describe(a), a, s)
            saved = screen.loads((base / name / 'got.screen').read_text())
            assert not screen.compare(saved, frame)
            frame['modes']['synchronized-output'] = 0
            expected = blank(12, 4)
            expected['title'] = b'probe'.hex()
            context = entry['context']
            if context == 'ascii':
                expected['rows'][0][0] = [1, 'U+0061', '-']
                expected['extents'][0] = 1
                expected['cursor']['col'] = 2
            elif context == 'wide':
                expected['rows'][0][:2] = [[2, 'U+4E2D', '-'], [0, '-', '-']]
                expected['extents'][0] = 2
                expected['cursor']['col'] = 3
            elif context == 'unwritten':
                expected['cursor']['col'] = 5
            assert not screen.compare(expected, frame)
            result.append((name, (base / (name + '.in')).read_bytes(), expected))
    assert len(result) == 12
    return result


if __name__ == '__main__':
    check()
    print('PASS frozen-annotation-controls complete-reference-frames12 hashes-twice no-marks-no-cell-no-cursor-change')
