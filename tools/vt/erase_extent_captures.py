#!/usr/bin/env python3
"""The 32 erase-extent boundary frames, taken from the reference with no correction.

The inputs are the two probes' (tests/vt/probes/erase_scroll_rows.py and
erase_span_bounds.py): partial erases after the ways a row can be made, and
erases bounded by what was printed and painted in their span. The captures
were taken with the reference's jump scroll off. With it on, the reference left
some of these erases uncounted depending on how its reads split the input
(warren#25), and the old D14 rule corrected those extents. Now the reference's
frame is the expectation, as it stands, apart from the D7 step every reference
frame gets: the reference does not know mode 2026, so synchronized-output is
expected as warren reports it. The three resized captures keep their own D6
contracts (tests/vt/d14_resize_expected.py): the reference does not reflow.
"""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tools/vt', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle  # noqa: E402
import screen  # noqa: E402
from chunking_suite import events  # noqa: E402
from d14_resize_expected import resized  # noqa: E402
BASE = ROOT / 'tests/vt/reference/erase-extents'
CAPTURES = {'scroll': 'erase_scroll_rows.py', 'span': 'erase_span_bounds.py'}
HEAD = '72e62d4'


def cases():
    """(name, input, replay, expected frame, labels) for each of the 32 captures, after checking every file."""
    output = []
    for capture, script in CAPTURES.items():
        base = BASE / capture
        manifest = json.loads((base / 'manifest.json').read_text())
        assert manifest['schema'] == 1 and manifest['errors'] == []
        assert manifest['dump_budget'] == 16 and manifest['terminal_process_budget'] == 32
        assert manifest['capture_head'].startswith(HEAD) and len(manifest['capture_head']) == 40
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
            sizes = [value for kind, value in stream if kind == 'r']
            if sizes:
                assert sizes == [(6, 8)] and stream[0] == ('size', (12, 4))
                assert not screen.compare(resized(name, reference=True), reference)
                expected, labels = resized(name), ['D6']
            else:
                expected, labels = reference, []
            output.append((capture + '-' + name, data, replay, expected, labels))
            captured['cases'][name].pop('files')
        assert {str(path.relative_to(base)) for path in base.rglob('*') if path.is_file()} == seen
        assert hashlib.sha256((json.dumps(captured, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    assert len(output) == 32
    return output


if __name__ == '__main__':
    cases()
    print('PASS erase-extent-captures scroll16 span16 hashes-twice uncorrected-reference D6-resizes-separately-constructed')
