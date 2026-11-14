#!/usr/bin/env python3
"""Generate the oracle's normal combining predicate from pinned UnicodeData."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from generate_assigned import assigned


def combining(data):
    assigned(data)  # Reuse strict scalar order, field-count and First/Last checks.
    ranges = []
    pending = None
    for raw in data.decode('utf-8').splitlines():
        if not raw:
            continue
        fields = raw.split(';')
        cp = int(fields[0], 16)
        name, category = fields[1:3]
        ccc = int(fields[3])
        if not 0 <= ccc <= 255:
            raise ValueError('canonical combining class outside0..255')
        if name.endswith(', First>'):
            pending = (cp, ccc)
            continue
        first = cp
        if name.endswith(', Last>'):
            first, first_ccc = pending
            if first_ccc != ccc:
                raise ValueError('First/Last combining class differs')
            pending = None
        if category == 'Cs' or not (category in ('Mn', 'Me') or ccc != 0):
            continue
        if ranges and ranges[-1][1] + 1 == first:
            ranges[-1][1] = cp
        else:
            ranges.append([first, cp])
    return {'ranges': ranges, 'scalars': sum(high - low + 1 for low, high in ranges)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True)
    parser.add_argument('--out', type=Path, default=ROOT / 'tests/vt/combining-ranges.json')
    args = parser.parse_args()
    pins = json.loads((ROOT / 'tests/vt/unicode-sources.json').read_text())
    source = next(item for item in pins['sources'] if item['name'] == 'UnicodeData.txt')
    data = args.data.read_bytes()
    for _ in range(2):
        if hashlib.sha256(data).hexdigest() != source['sha256']:
            parser.error('UnicodeData digest differs from the normative pin')
    result = {'schema': 1, 'version': pins['version'], 'source_sha256': source['sha256'],
              'predicate': 'Mn/Me or nonzero canonical combining class', **combining(data)}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('COMBINING-DATA unicode=%s scalars=%d ranges=%d source-sha256=%s' %
          (result['version'], result['scalars'], len(result['ranges']), source['sha256']))


if __name__ == '__main__':
    main()
