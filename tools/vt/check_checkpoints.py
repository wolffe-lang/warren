#!/usr/bin/env python3
"""Bind captured ASCII/colour/recording-resize checkpoints to owned inputs."""
import copy
import hashlib
import json
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'tests/vt/reference/checkpoints'


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    generated = runpy.run_path(str(ROOT / 'tests/vt/probes/colour_and_checkpoints.py'))['cases']()
    assert manifest['schema'] == 1 and manifest['complete_dump_count'] == 11 and not manifest['errors']
    assert set(manifest['cases']) == set(generated)
    assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    original = copy.deepcopy(manifest)
    original.pop('capture_head')
    original.pop('capture_manifest_sha256')
    seen = {'manifest.json'}
    for name, (data, cols, rows, provenance) in generated.items():
        entry = manifest['cases'][name]
        assert entry['size'] == [cols, rows]
        for key, value in provenance.items():
            assert entry[key] == value, (name, key)
        path = name + ('.rec' if data.startswith(b'warren-rec 1\n') else '.in')
        assert entry['input_path'] == path
        assert entry['input_sha256'] == hashlib.sha256(data).hexdigest()
        assert (BASE / path).read_bytes() == data
        expected = {name + '/' + file for file in ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json', 'got.screen')}
        expected.add(path)
        assert set(entry['files']) == expected
        assert entry['screen_sha256'] == entry['files'][name + '/got.screen']
        for relative, digest in entry['files'].items():
            file = BASE / relative
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            assert file.is_file() and not file.is_symlink() and file.stat().st_size <= 1048576
            for _ in range(2):
                assert hashlib.sha256(file.read_bytes()).hexdigest() == digest, relative
        seen.update(expected)
        original['cases'][name].pop('files')
        original['cases'][name].pop('input_path')
    assert {str(file.relative_to(BASE)) for file in BASE.rglob('*') if file.is_file()} == seen
    encoded = (json.dumps(original, indent=2) + '\n').encode()
    assert hashlib.sha256(encoded).hexdigest() == manifest['capture_manifest_sha256']
    return manifest


if __name__ == '__main__':
    check()
    print('PASS frozen-checkpoints cases=11 inputs+raw-replies+prints+screens+pins hashes-twice')
