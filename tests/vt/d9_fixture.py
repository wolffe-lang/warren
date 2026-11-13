"""D9 fixture definitions and exact reference-delta bounds, independent of native output."""
import copy
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import screen
from expectations import blank, text_row
from inverse_expected import expected as inverse_expected

E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'
BOUNDS = {'fuzz-0010': ('bg=idx:15540094', 'bg=idx:0', 6),
          'fuzz-0016': ('bg=idx:181', None, 1903),
          'fuzz-0019': ('bg=idx:226', None, 19)}


def background(attrs):
    return next((part for part in attrs.split(',') if part.startswith('bg=')), None)


def with_background(attrs, value):
    parts = [part for part in attrs.split(',') if part != '-' and not part.startswith('bg=')]
    if value:
        parts.append(value)
    return ','.join(parts) or '-'


def complex_bound(name, original):
    old, new, count = BOUNDS[name]
    cells = {(r + 1, c + 1) for r, row in enumerate(original['rows']) for c, cell in enumerate(row)
             if background(cell[2]) == old}
    assert len(cells) == count, (name, len(cells), count)
    return cells, new


def verify_background_delta(original, repaired, cells, value):
    """The exact declared cell set and ONLY its background field may change."""
    assert original['size'] == repaired['size']
    actual = {(r + 1, c + 1) for r, row in enumerate(original['rows']) for c, cell in enumerate(row)
              if background(cell[2]) != background(repaired['rows'][r][c][2])}
    assert actual == cells, ('D9-reference-cell-bound', sorted(actual ^ cells)[:20])
    written = copy.deepcopy(original)
    for row, col in cells:
        written['rows'][row - 1][col - 1][2] = with_background(written['rows'][row - 1][col - 1][2], value)
    differences = screen.compare(written, repaired)
    assert not differences, ('D9-reference-only-background-field', differences[:20])


def one_x(attrs):
    result = blank(12, 4)
    result['title'] = b'probe'.hex()
    text_row(result, 0, [88], attrs)
    result['cursor']['col'] = 2
    return result


def definitions():
    repair = runpy.run_path(str(ROOT / 'tools/vt/repair_background_fixture.py'))['repair']
    inverse = runpy.run_path(str(ROOT / 'tests/vt/probes/default_restoration.py'))['inverse_cases']()
    result = {}
    for name, (data, cols, rows) in inverse.items():
        fixed, events = repair(data)
        result['minimal-' + name] = {'kind': 'minimal-repaired', 'original': data, 'input': fixed,
            'size': [cols, rows], 'injections': events, 'original_case': name,
            'written': inverse_expected(name), 'pen_status': False}
    fuzz = runpy.run_path(str(ROOT / 'tools/corpus/fuzz.py'))['stream']
    for seed in (10, 16, 19):
        data = fuzz(seed, 2048)
        fixed, events = repair(data)
        name = 'fuzz-%04d' % seed
        result[name] = {'kind': 'complex-repaired', 'original': data, 'input': fixed,
            'size': [80, 24], 'injections': events, 'pen_status': False}
    setters = {'extended-palette': (b'48;5;2', 'bg=idx:2'),
               'basic-palette': (b'42', 'bg=idx:2'),
               'bright-palette': (b'102', 'bg=idx:10'),
               'default': (b'49', ''), 'rgb': (b'48;2;1;2;3', 'bg=rgb:1:2:3')}
    prefix = HEAD + C + b'40m' + E + b'7' + C + b'48;2;237;31;126m' + E + b'8'
    for inverse_code in (7, 27):
        for label, (setter, attr) in setters.items():
            for order in ('inverse-first', 'background-first'):
                inv = str(inverse_code).encode()
                parameters = inv + b';' + setter if order == 'inverse-first' else setter + b';' + inv
                data = prefix + C + parameters + b'mX'
                attrs = ','.join(part for part in ('inverse' if inverse_code == 7 else '', attr) if part) or '-'
                result['background-%d-%s-%s' % (inverse_code, label, order)] = {
                    'kind': 'mixed-background-measurement', 'original': data, 'input': data,
                    'size': [12, 4], 'injections': [], 'written': one_x(attrs), 'pen_status': True}
    for name, setter in (('bright-blue-basic-bold', b'1;94'), ('bright-blue-indexed-bold', b'1;38;5;12')):
        data = HEAD + C + setter + b'mX'
        result[name] = {'kind': 'bright-report-measurement', 'original': data, 'input': data,
            'size': [12, 4], 'injections': [], 'written': one_x('bold,fg=idx:12'), 'pen_status': True}
    assert len(result) == 37 and sum(entry['pen_status'] for entry in result.values()) == 22
    return result
