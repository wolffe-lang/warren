"""Source-bounded written expectations for report-limited recording checkpoints."""
import copy
import re
from chunking_suite import events


def foreground_palette(data, replay=True):
    output = b''.join(value for kind, value in events(data, replay) if kind == 'o')
    declared = set()
    for match in re.finditer(rb'\x1b\[([0-9:;]*)m', output):
        assert b':' not in match[1], 'this owned fixture uses semicolon SGR only'
        values = [int(part or b'0') for part in match[1].split(b';')]
        at = 0
        while at < len(values):
            code = values[at]
            if code in (38, 48):
                assert at + 1 < len(values) and values[at + 1] in (2, 5)
                count = 1 if values[at + 1] == 5 else 3
                assert at + count + 2 <= len(values)
                if code == 38:
                    if count == 1:
                        declared.add(values[at + 2])
                    else:
                        rgb = values[at + 2:at + 5]
                        assert all(0 <= value <= 255 for value in rgb)
                        assert rgb[0] * 65536 + rgb[1] * 256 + rgb[2] > 255, 'small RGB cache values would make this limited-form proof ambiguous'
                at += count + 2
                continue
            if 30 <= code <= 37:
                declared.add(code - 30)
            elif 90 <= code <= 97:
                declared.add(code - 90 + 8)
            at += 1
    return declared


def source_bright_forms(data, frame, replay, declared_expected):
    result = copy.deepcopy(frame)
    labels = []
    declared = foreground_palette(data, replay)
    assert declared == declared_expected
    # No low counterpart is ever set by this input. The corresponding bright
    # set form is therefore unambiguous despite print-screen folding it.
    replacements = {value - 8: value for value in declared if 8 <= value <= 15 and value - 8 not in declared}
    corrected = 0
    for row in result['rows']:
        for cell in row:
            parts = cell[2].split(',')
            if 'bold' not in parts:
                continue
            for index, part in enumerate(parts):
                if part.startswith('fg=idx:') and int(part[7:]) in replacements:
                    parts[index] = 'fg=idx:%d' % replacements[int(part[7:])]
                    corrected += 1
            cell[2] = ','.join(parts)
    assert corrected > 0
    labels.append('RPT-BRIGHT-BOLD-COLOUR')
    return labels, result


def written_checkpoint(name, data, frame):
    if name == 'recording-quarry-resize-1':
        return source_bright_forms(data, frame, True, {0, 11, 12, 14})
    return [], copy.deepcopy(frame)


def written_fuzz_bright(name, data, frame):
    declared = {'fuzz-0003': {3, 4, 9, 10, 13, 182},
                'fuzz-0022': {5, 8, 10, 16, 134, 217}}
    if name in declared:
        return source_bright_forms(data, frame, False, declared[name])
    return [], copy.deepcopy(frame)
