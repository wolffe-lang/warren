"""Load the independent repaired-reference frame, never candidate output."""
import hashlib
import json
from pathlib import Path
import screen
from d9_fixture import BOUNDS, complex_bound, verify_background_delta

BASE = Path(__file__).resolve().parent / 'reference/d9'


def written_d9(name, data, original):
    if name not in BOUNDS:
        return [], original
    manifest = json.loads((BASE / 'manifest.json').read_text())
    entry = manifest['cases'][name]
    assert hashlib.sha256(data).hexdigest() == entry['original_sha256']
    assert (BASE / (name + '.original.in')).read_bytes() == data
    raw = (BASE / name / 'got.screen').read_bytes()
    assert hashlib.sha256(raw).hexdigest() == entry['screen_sha256']
    repaired = screen.loads(raw.decode())
    cells, value = complex_bound(name, original)
    verify_background_delta(original, repaired, cells, value)
    return ['D9'], repaired
