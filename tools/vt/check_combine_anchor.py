#!/usr/bin/env python3
"""Retain114 anchor observations; compare113, keeping RI+HT explicitly open.

D10 reconstructs only a written extent from the declared mark target; every
base, mark, rendition, cursor and mode still comes from strict raw A/S checks.
No candidate output is an input to this fixture.
"""
import copy
import hashlib
import json
from pathlib import Path
import runpy
import sys
ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tools/vt', 'tests/vt', 'tests/vt/probes'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle
import screen
from chunking_suite import events
from expectations import blank
from combining_placement import full_cell_observations
from erase_extent_fixture import trace
BASE = ROOT / 'tests/vt/reference/combine-anchor'
PLACEMENT = {'cup-unwritten-left': 5, 'cup-written-left': 5, 'print-written-left': 4,
    'print-written-blank-left': 4, 'cup-written-blank-left': 5, 'cup-erased-left': 5,
    'cup-gap-left': 5, 'cup-painted-left': 5, 'print-wide-tail-left': 3,
    'cup-wide-tail-left': 5, 'cup-first-empty': 1, 'cr-first-empty': 1,
    'cr-first-written': 1, 'cup-first-written': 1, 'pending-unwritten-left': 12,
    'pending-written-left': 12, 'pending-wide-tail-under': 11,
    'clear-last-unwritten-left': 12, 'clear-last-written-left': 12,
    'clear-last-wide-tail-under': 11, 'pending-first-column': 1, 'clear-first-column': 1}
CLEARS = {name: (1, 4) for name in ('baseline', 'bs', 'ht', 'sgr', 'save', 'alt47-enter',
    'alt47-roundtrip', 'second-mark', 'motion-D-0', 'motion-D-1', 'resize-same',
    'resize-narrow', 'pending-baseline', 'pending-ech-through-anchor',
    'pending-el-through-anchor', 'pending-sgr')}
CLEARS.update({name: (1, 5) for name in ('cup-same', 'ech-not-anchor', 'el-not-anchor',
    'el-through-anchor', 'save-restore-same', 'alt1049-enter', 'alt1049-roundtrip',
    'alt1049-print-return', 'cup-then-second-mark', 'motion-A-0', 'motion-A-1')})
CLEARS.update({'cr': (1, 1), 'lf': (2, 5), 'restore-earlier': (1, 1),
    'motion-C-0': (1, 6), 'motion-C-1': (1, 6), 'motion-B-0': (2, 5), 'motion-B-1': (2, 5)})
FOLLOWUPS = {name: (1, 9) for name in ('bs-then-ht', 'cub0-then-ht', 'cub1-then-ht', 'ich-then-ht', 'dch-then-ht')}
FOLLOWUPS.update({'su-then-ht': (1, 4), 'sd-then-ht': (1, 4), 'ind-then-ht': (2, 9),
    'nel-then-ht': (2, 9), 'alt1047-roundtrip': (1, 5), 'cup-new-style': (1, 5),
    'cr-new-style': (1, 1), 'resize-wrapped-anchor': (2, 4)})


def finish_d10(a, s, scalar, target):
    partial = oracle.describe(a)
    try:
        return oracle.finish(copy.deepcopy(partial), a, s), False
    except oracle.OracleError as error:
        assert str(error) == 'row %d: unprinted cell %d is not blank' % target
    cols, rows = partial['size']
    tails = [[c + 1 for c, checksum in enumerate(row) if checksum == '0000'] for row in a['checksums']]
    observations = full_cell_observations(s, tails, cols, rows, scalar)
    assert len(observations) == 1 and observations[0][:2] == list(target)
    chars = observations[0][2]
    r, c = target[0] - 1, target[1] - 1
    assert a['checksums'][r][c] == '%04X' % (-chars[0] & 0xFFFF)
    # The independent D10 rule writes this exact target. A's other extents and
    # cells remain intact; S must agree with all of them and every rendition.
    while len(partial['rows'][r]) <= c:
        partial['rows'][r].append([1, 'U+0020', '-', False])
    partial['rows'][r][c][1] = oracle.code_points(chars)
    partial['extents'][r] = max(partial['extents'][r], c + partial['rows'][r][c][0])
    return oracle.finish(partial, a, s), True


def wrapped_contract():
    result = blank(6, 8)
    result['title'] = b'probe'.hex()
    for index, cp in enumerate(b'abcdefghijklmnop'):
        r, c = divmod(index, 6)
        result['rows'][r][c] = [1, 'U+%04X' % cp, '-']
        result['extents'][r] = c + 1
    result['rows'][2][3][1] += '+U+0301'
    result['cursor'].update(row=3, col=5)
    return result


def check():
    definitions = runpy.run_path(str(ROOT / 'tests/vt/probes/combining_placement.py'))['cases']()
    ops = runpy.run_path(str(ROOT / 'tests/vt/probes/combine_anchor_clear.py'))
    groups = {'placement': (definitions, 134, 'efcb5fa'),
              'clears': (ops['cases'](), 69, 'a65800e'),
              'followups': (ops['followup_cases'](), 29, '086f13e')}
    result = []
    for group, (cases, budget, head) in groups.items():
        base = BASE / group
        manifest = json.loads((base / 'manifest.json').read_text())
        assert manifest['schema'] == 1 and manifest['terminal_process_budget'] == budget
        assert manifest['capture_head'].startswith(head) and len(manifest['capture_head']) == 40
        assert manifest['errors'] == (['ri-then-ht'] if group == 'followups' else [])
        assert manifest['pins_sha256'] == hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest()
        assert set(manifest['cases']) == set(cases)
        captured = copy.deepcopy(manifest)
        for field in ('capture_head', 'pins_sha256', 'capture_manifest_sha256', 'support_files'):
            captured.pop(field)
        seen = {'manifest.json'}
        for relative, wanted in manifest['support_files'].items():
            assert relative in ('status.json', 'status-1.json', 'status-12.json')
            for _ in range(2):
                assert hashlib.sha256((base / relative).read_bytes()).hexdigest() == wanted
            seen.add(relative)
        for name, definition in cases.items():
            entry = manifest['cases'][name]
            if group == 'placement':
                prefix, scalar, context, cols, rows = definition
                data, replay, target = prefix + chr(scalar).encode(), False, (1, PLACEMENT[context])
            else:
                source_events, cols, rows = definition
                data, replay, scalar = ops['encode'](source_events, cols, rows), True, 0x301
                target = (CLEARS if group == 'clears' else FOLLOWUPS).get(name)
            suffix = '.rec' if replay else '.in'
            assert (base / (name + suffix)).read_bytes() == data
            assert entry['input_sha256'] == hashlib.sha256(data).hexdigest()
            expected_files = {name + suffix} | {name + '/' + part for part in
                ('A.json', 'S.json', 'A.print', 'S.print', 'continuation.json')}
            if entry.get('classification') == 'complete-reference-frame':
                expected_files.add(name + '/got.screen')
            assert set(entry['files']) == expected_files
            for relative, wanted in entry['files'].items():
                path = base / relative
                assert not Path(relative).is_absolute() and '..' not in Path(relative).parts
                assert path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576
                for _ in range(2):
                    assert hashlib.sha256(path.read_bytes()).hexdigest() == wanted
            seen.update(expected_files)
            a = json.loads((base / name / 'A.json').read_text())
            s = json.loads((base / name / 'S.json').read_text())
            a['print'] = (base / name / 'A.print').read_bytes()
            s['print'] = (base / name / 'S.print').read_bytes()
            status = entry['status']
            assert status['before'] == status['after'], 'zero-width mark changed measured cursor state'
            if name == 'ri-then-ht' and group == 'followups':
                assert status['before']['cpr_hex'] == b'\x1b[1;9R'.hex()
                assert a['cpr'] == '\x1b[1;10R' and a['checksums'][0][8] == 'FCFF'
                payload = b''.join(value for kind, value in events(data, True) if kind == 'o')
                assert trace(payload, cols, rows)['reference_exclusions']
                try:
                    oracle.describe(a)
                except oracle.OracleError:
                    pass
                else:
                    raise AssertionError('the open RI report unexpectedly became consistent')
                captured['cases'][name].pop('files')
                continue
            assert a['cpr'].encode().hex() == status['after']['cpr_hex']
            tails = [[c + 1 for c, checksum in enumerate(row) if checksum == '0000'] for row in a['checksums']]
            observed = full_cell_observations(s, tails, *a['size'], scalar)
            assert observed == entry['observed_mark_cells']
            assert len(observed) == 1 and observed[0][:2] == list(target)
            frame, d10 = finish_d10(a, s, scalar, target)
            frame['modes']['synchronized-output'] = 0
            labels = ['D10'] if d10 else []
            if name == 'resize-wrapped-anchor' and group == 'followups':
                frame = wrapped_contract()
                labels.append('D6')
            result.append((group + '-' + name, data, replay, cols, rows, frame, labels))
            captured['cases'][name].pop('files')
        assert {str(path.relative_to(base)) for path in base.rglob('*') if path.is_file()} == seen
        assert hashlib.sha256((json.dumps(captured, indent=2) + '\n').encode()).hexdigest() == manifest['capture_manifest_sha256']
    assert len(result) == 113
    return result


if __name__ == '__main__':
    check()
    print('PASS frozen-combine-anchor observations114 comparable113 RI-question1 hashes-twice D10-only-written-extents D6-logical-remap')
