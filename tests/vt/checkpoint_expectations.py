"""Source-bounded written expectations for report-limited recording checkpoints."""
import copy
import re
from chunking_suite import events


def foreground_palette(data):
    output = b''.join(value for kind, value in events(data, True) if kind == 'o')
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
                    assert count == 1, 'RGB foreground is outside this palette-form proof'
                    declared.add(values[at + 2])
                at += count + 2
                continue
            if 30 <= code <= 37:
                declared.add(code - 30)
            elif 90 <= code <= 97:
                declared.add(code - 90 + 8)
            at += 1
    return declared


def written_checkpoint(name, data, frame):
    result = copy.deepcopy(frame)
    labels = []
    if name != 'recording-quarry-resize-1':
        return labels, result
    declared = foreground_palette(data)
    assert declared == {0, 11, 12, 14}
    # No low counterpart is ever set by this input. The corresponding bright
    # set form is therefore unambiguous despite print-screen folding it.
    replacements = {value - 8: value for value in declared if value >= 8 and value - 8 not in declared}
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
