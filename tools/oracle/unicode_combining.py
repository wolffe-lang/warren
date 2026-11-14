"""Unicode15.1 print-cluster classes; never use the host's Unicode database."""
from bisect import bisect_right
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_DATA = json.loads((ROOT / 'tests/vt/combining-ranges.json').read_text())
_PINS = json.loads((ROOT / 'tests/vt/unicode-sources.json').read_text())
_SOURCE = next(item for item in _PINS['sources'] if item['name'] == 'UnicodeData.txt')
assert _DATA['schema'] == 1 and _DATA['version'] == _PINS['version'] == '15.1.0'
assert _DATA['source_sha256'] == _SOURCE['sha256']
assert _DATA['predicate'] == 'Mn/Me or nonzero canonical combining class'
_RANGES = _DATA['ranges']
_previous = -1
for _low, _high in _RANGES:
    assert 0 <= _low <= _high <= 0x10FFFF and _low > _previous
    assert _high < 0xD800 or _low > 0xDFFF
    _previous = _high
assert sum(high - low + 1 for low, high in _RANGES) == _DATA['scalars']
_STARTS = [low for low, _ in _RANGES]
UNICODE_VERSION = _DATA['version']


def normal_combining(cp):
    index = bisect_right(_STARTS, cp) - 1
    return index >= 0 and cp <= _RANGES[index][1]
