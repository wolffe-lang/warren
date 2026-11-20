#!/usr/bin/env python3
"""Bind D15's frozen reference observations and their bound.

Each case's original and split inputs, raw reference passes, prints and screens
are hashed twice against the manifest. On every trigger case the reference's
frames for the two inputs must differ in exactly the one cell the D15 bound
permits; warren's written frame must equal the split input's reference frame
and must still differ from the original input's. Controls meet no trigger.
"""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tools/vt', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle  # noqa: E402
import screen  # noqa: E402
from d15_fixture import definitions  # noqa: E402
from fresh_expectations import dch_pair  # noqa: E402

BASE = ROOT / 'tests/vt/reference/d15'
PASS_FILES = ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json', 'got.screen')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def observed(name, label):
    """The reference's frame, rebuilt from the raw passes, equal to the recorded screen."""
    work = BASE / name / label
    a = json.loads((work / 'A.json').read_text())
    s = json.loads((work / 'S.json').read_text())
    a['print'] = (work / 'A.print').read_bytes()
    s['print'] = (work / 'S.print').read_bytes()
    frame = oracle.finish(oracle.describe(a), a, s)
    assert not screen.compare(screen.loads((work / 'got.screen').read_text()), frame), (name, label)
    return frame


def reported(frame):
    """D7: the reference does not know mode 2026; no input here sets it."""
    frame = copy.deepcopy(frame)
    frame['modes']['synchronized-output'] = 0
    return frame


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    generated = definitions()
    assert manifest['schema'] == 1 and manifest['errors'] == []
    assert manifest['pins_sha256'] == digest((ROOT / 'warren-oracle.toml').read_bytes())
    assert manifest['fixture_sha256'] == digest((ROOT / 'tools/vt/dch_tail_fixture.py').read_bytes())
    assert len(manifest['capture_head']) == 40
    assert set(manifest['cases']) == set(generated)
    captured = copy.deepcopy(manifest)
    captured.pop('capture_head')
    captured.pop('capture_manifest_sha256')
    seen = {'manifest.json'}
    counts = {'trigger': 0, 'control': 0}
    for name, definition in generated.items():
        entry = manifest['cases'][name]
        assert entry['kind'] == definition['kind'] and entry['size'] == definition['size']
        assert entry['edits'] == definition['edits']
        for key, suffix in (('original', '.original.in'), ('input', '.in')):
            raw = (BASE / (name + suffix)).read_bytes()
            assert raw == definition[key] and digest(raw) == entry[key + '_sha256'], (name, key)
        labels = ('original', 'split') if definition['kind'] == 'trigger' else ('original',)
        files = {name + '.original.in', name + '.in'}
        files |= {'%s/%s/%s' % (name, label, part) for label in labels for part in PASS_FILES}
        assert set(entry['files']) == files, sorted(set(entry['files']) ^ files)
        for relative, wanted in entry['files'].items():
            path = BASE / relative
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            assert path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576
            for _ in range(2):
                assert digest(path.read_bytes()) == wanted, relative
        original = observed(name, 'original')
        if definition['kind'] == 'trigger':
            split = observed(name, 'split')
            expected, detail = dch_pair(definition['original'], original, split)
            assert len(detail['cells']) == 1 and entry['bound_cells'] == [cell[:2] for cell in detail['cells']], name
            assert not screen.compare(definition['written'], reported(expected)), name
            assert not screen.compare(definition['written'], reported(split)), name
            assert screen.compare(definition['written'], reported(original)), ('the reference keeps the cell', name)
        else:
            assert entry['bound_cells'] == [] and definition['input'] == definition['original'], name
        counts[definition['kind']] += 1
        seen |= files
        captured['cases'][name].pop('files')
    assert {str(path.relative_to(BASE)) for path in BASE.rglob('*') if path.is_file()} == seen
    assert digest((json.dumps(captured, indent=2) + '\n').encode()) == manifest['capture_manifest_sha256']
    return counts


if __name__ == '__main__':
    counts = check()
    print('PASS frozen-d15 triggers=%d controls=%d original+split-inputs raw-passes+prints+screens hashes-twice '
          'one-cell-bound written-equals-split' % (counts['trigger'], counts['control']))
