"""Source-triggered paired-reference bounds for the live fuzz drive."""
import copy
import hashlib
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tools/vt', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import screen
from d9_fixture import background, with_background
from repair_background_fixture import repair as repair_background
from legacy_black_fixture import repair as repair_legacy
from report_fixture import controls, tab_operations, column_one
from report_expectations import parts, foreground, replace_foreground, with_tab_one


def d9_triggers(data):
    _, restores = repair_background(data)
    tokens = [(event['original_offset'], 0, 'restore', event) for event in restores]
    for match in controls(data, rb'\x1b\[([0-9;]*)m|\x1bc|\x1b\[!p'):
        tokens.append((match.start(), 1, 'sgr' if match[0].endswith(b'm') else 'reset', match))
    armed = None
    result = []
    for offset, _, kind, value in sorted(tokens, key=lambda item: item[:2]):
        if kind == 'restore':
            armed = value
            continue
        if kind == 'reset':
            armed = None
            continue
        values = [int(part or b'0') for part in value[1].split(b';')]
        at = 0
        bg = inverse = False
        while at < len(values):
            code = values[at]
            if code in (38, 48, 58):
                if at + 1 >= len(values) or values[at + 1] not in (2, 5):
                    raise ValueError('unsupported source colour form')
                length = 3 if values[at + 1] == 5 else 5
                if at + length > len(values):
                    raise ValueError('truncated source colour')
                bg |= code == 48
                at += length
                continue
            inverse |= code in (7, 27)
            bg |= code in (0, 49) or 40 <= code <= 47 or 100 <= code <= 107
            at += 1
        if armed is not None and inverse and not bg:
            result.append({'offset': offset, 'restore_offset': armed['original_offset'],
                           'restored_background': armed['background']})
            armed = None
        elif bg:
            armed = None
    return result


def background_pair(data, original, repaired):
    _, injections = repair_background(data)
    triggers = d9_triggers(data)
    expected = copy.deepcopy(original)
    cells = []
    assert original['size'] == repaired['size']
    for r, row in enumerate(original['rows']):
        for c, cell in enumerate(row):
            old, new = background(cell[2]), background(repaired['rows'][r][c][2])
            if old != new:
                assert injections and triggers, 'D9 change without its source restore/inverse trigger'
                cells.append([r + 1, c + 1, old, new])
                expected['rows'][r][c][2] = with_background(cell[2], new)
    differences = screen.compare(expected, repaired)
    assert not differences, ('D9 paired reference changed a non-background field', differences[:20])
    return expected, {'triggers': triggers, 'injections': injections, 'cells': cells}


def legacy_pair(data, original, repaired):
    _, edits = repair_legacy(data)
    expected = copy.deepcopy(original)
    cells = []
    assert original['size'] == repaired['size']
    for r, row in enumerate(original['rows']):
        for c, cell in enumerate(row):
            # Apply existing N1 before bounding observable foreground changes,
            # just as recompose_no_bold does. Keep unobservable raw cells intact.
            before = parts(screen.normalise(cell)[2])
            after = parts(screen.normalise(repaired['rows'][r][c])[2])
            old, new = foreground(before), foreground(after)
            if old != new:
                assert edits, 'D13 correction without a source legacy30 setter'
                assert 'bold' in before and 'bold' in after
                assert old == 'fg=idx:8' and new == 'fg=idx:0', 'D13 wrong direction or foreground value'
                cells.append([r + 1, c + 1, old, new])
                expected['rows'][r][c][2] = ','.join(replace_foreground(before, new))
    differences = screen.compare(expected, repaired)
    assert not differences, ('D13 paired reference changed another field', differences[:20])
    return expected, {'source_edits': edits, 'cells': cells}


def measured_tabs(data, reference, record):
    operations = tab_operations(data)
    assert record['input_sha256'] == hashlib.sha256(data).hexdigest()
    assert len(record['positions']) == len(operations)
    for operation, position in zip(operations, record['positions']):
        for field in ('offset', 'end', 'kind'):
            assert position[field] == operation[field]
        assert 1 <= position['row'] <= reference['size'][1]
    present = column_one(operations, [position['col'] for position in record['positions']])
    assert record['tab_one'] == present
    return with_tab_one(reference, present), {'source_operations': operations,
                                             'tab_one': present,
                                             'positions': record['positions']}
