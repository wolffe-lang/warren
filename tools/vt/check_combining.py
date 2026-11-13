#!/usr/bin/env python3
"""Keep D10's six strict reference-report failures and two strict controls."""
import copy
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import run as oracle
import screen
from combining_cases import cases
from combining_expected import expected
BASE = ROOT / 'tests/vt/reference/combining'
FAILURES = {'unwritten-primary': 5, 'unwritten-alternate': 5, 'unwritten-resized': 5,
            'column-zero': 1, 'after-erase': 4, 'last-column-addressed': 12}


def check():
    manifest = json.loads((BASE / 'manifest.json').read_text())
    assert manifest['schema'] == 1 and manifest['complete_dump_count'] == 8
    assert set(manifest['errors']) == set(FAILURES)
    assert set(manifest['cases']) == set(cases())
    assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
    captured = copy.deepcopy(manifest)
    captured.pop('capture_head')
    captured.pop('capture_manifest_sha256')
    seen = {'manifest.json'}
    for name, (data, cols, rows, provenance) in cases().items():
        entry = manifest['cases'][name]
        assert entry['size'] == [cols, rows]
        for key, value in provenance.items():
            assert entry[key] == value
        suffix = '.rec' if name == 'unwritten-resized' else '.in'
        assert (BASE / (name + suffix)).read_bytes() == data
        assert hashlib.sha256(data).hexdigest() == entry['input_sha256']
        files = {name + suffix} | {name + '/' + part for part in ('A.json','S.json','A.print','S.print','continuation.json')}
        if name not in FAILURES:
            files.add(name + '/got.screen')
        assert set(entry['files']) == files
        for relative, digest in entry['files'].items():
            file = BASE / relative
            assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
            assert file.is_file() and not file.is_symlink() and file.stat().st_size <= 1048576
            for _ in range(2):
                assert hashlib.sha256(file.read_bytes()).hexdigest() == digest
        a = json.loads((BASE / name / 'A.json').read_text())
        s = json.loads((BASE / name / 'S.json').read_text())
        a['print'] = (BASE / name / 'A.print').read_bytes()
        s['print'] = (BASE / name / 'S.print').read_bytes()
        if name in FAILURES:
            message = 'row 1: unprinted cell %d is not blank' % FAILURES[name]
            assert entry['error'] == message
            partial = oracle.describe(a)
            partial['modes']['synchronized-output'] = 0
            contract = expected(name)
            for field in ('size', 'cursor', 'region', 'tabs', 'title', 'modes'):
                assert partial[field] == contract[field], (name, field)
            try:
                oracle.finish(oracle.describe(a), a, s)
            except oracle.OracleError as error:
                assert str(error) == message
            else:
                raise AssertionError(('strict validator no longer rejects the inconsistent report', name))
            assert a['print'] == b'\r\n' * a['size'][1]
            # Observation only, never used to manufacture an expected frame:
            # the first original full-cell row keeps the acute at the addressed
            # cursor column, including after the 12x2 -> 6x4 resize.
            full = oracle.parse_print(s['print'], a['size'][1])[0]
            assert full[FAILURES[name] - 1][0] == [32, 769]
        else:
            got = oracle.finish(oracle.describe(a), a, s)
            assert not screen.compare(screen.loads((BASE / name / 'got.screen').read_text()), got)
            got['modes']['synchronized-output'] = 0
            assert not screen.compare(expected(name), got)
        seen.update(files)
        captured['cases'][name].pop('files')
    assert {str(path.relative_to(BASE)) for path in BASE.rglob('*') if path.is_file()} == seen
    assert hashlib.sha256((json.dumps(captured, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    return manifest


if __name__ == '__main__':
    check()
    print('PASS frozen-combining strict-report-failures=6 strict-controls=2 hashes-twice original-validator-retained reference-after-resize-acute-kept-at-row1-col5')
