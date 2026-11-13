#!/usr/bin/env python3
"""Bind32 D14 boundary captures; only source-declared extents may differ."""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tools/vt', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle
import screen
from chunking_suite import events
from d14_resize_expected import resized
from erase_extent_fixture import apply, trace
BASE = ROOT / 'tests/vt/reference/erase-extents'
CAPTURES = {'scroll': ('erase_scroll_rows.py', '449382c'),
            'span': ('erase_span_bounds.py', '0f724ee')}


def check():
    output = []
    for capture, (script, head) in CAPTURES.items():
        base = BASE / capture
        manifest = json.loads((base / 'manifest.json').read_text())
        assert manifest['schema'] == 1 and manifest['errors'] == []
        assert manifest['dump_budget'] == 16 and manifest['terminal_process_budget'] == 32
        assert manifest['capture_head'].startswith(head) and len(manifest['capture_head']) == 40
        assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
        sources = runpy.run_path(str(ROOT / 'tests/vt/probes' / script))['cases']()
        assert set(sources) == set(manifest['cases'])
        captured = copy.deepcopy(manifest)
        for key in ('capture_head', 'pins_sha256', 'capture_manifest_sha256'):
            captured.pop(key)
        seen = {'manifest.json'}
        for name, value in sources.items():
            data, replay = value if capture == 'span' else (value, False)
            entry = manifest['cases'][name]
            suffix = '.rec' if replay else '.in'
            assert (base / (name + suffix)).read_bytes() == data
            assert entry['input_sha256'] == hashlib.sha256(data).hexdigest()
            files = {name + suffix} | {name + '/' + part for part in
                ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json', 'got.screen')}
            assert set(entry['files']) == files
            for relative, wanted in entry['files'].items():
                path = base / relative
                assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
                assert path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576
                for _ in range(2):
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == wanted
            seen.update(files)
            a = json.loads((base / name / 'A.json').read_text())
            s = json.loads((base / name / 'S.json').read_text())
            a['print'] = (base / name / 'A.print').read_bytes()
            s['print'] = (base / name / 'S.print').read_bytes()
            reference = oracle.finish(oracle.describe(a), a, s)
            assert not screen.compare(screen.loads((base / name / 'got.screen').read_text()), reference)
            reference['modes']['synchronized-output'] = 0
            stream = events(data, True) if replay else [('size', (12, 4)), ('o', data)]
            payload = b''.join(value for kind, value in stream if kind == 'o')
            sizes = [value for kind, value in stream if kind == 'r']
            if sizes:
                assert sizes == [(6, 8)] and stream[0] == ('size', (12, 4))
                assert not screen.compare(resized(name, reference=True), reference)
                expected = resized(name)
                labels = ['D6'] + (['D14'] if trace(payload, 12, 4)['rows'] else [])
            else:
                expected, bounds = apply(payload, reference)
                labels = ['D14'] if bounds['rows'] else []
                # The correction is literally the declared row/extent fields;
                # no cell, rendition, cursor or other metadata is touched.
                for bound in bounds['rows']:
                    original = reference['extents'][bound['row'] - 1]
                    assert original == bound['reference_extent']
                for field in reference:
                    if field != 'extents':
                        assert expected[field] == reference[field]
            output.append((capture + '-' + name, data, replay, expected, labels))
            captured['cases'][name].pop('files')
        assert {str(path.relative_to(base)) for path in base.rglob('*') if path.is_file()} == seen
        assert hashlib.sha256((json.dumps(captured, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    assert len(output) == 32
    return output


if __name__ == '__main__':
    check()
    print('PASS frozen-D14 scroll16 span16 hashes-twice extent-only-source-bounds D6-resizes-separately-constructed')
