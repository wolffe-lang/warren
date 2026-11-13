#!/usr/bin/env python3
"""Derive assigned Unicode scalar ranges from the pinned normative data."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def assigned(data):
    ranges = []
    counts = Counter()
    excluded = 0
    pending = None
    previous = -1
    for number, raw in enumerate(data.decode('utf-8').splitlines(), 1):
        if not raw:
            continue
        fields = raw.split(';')
        if len(fields) != 15:
            raise ValueError('UnicodeData field count at line %d' % number)
        cp = int(fields[0], 16)
        name, category = fields[1:3]
        if not 0 <= cp <= 0x10FFFF or cp <= previous:
            raise ValueError('UnicodeData scalar order/domain at line %d' % number)
        previous = cp
        if name.endswith(', First>'):
            if pending:
                raise ValueError('nested First range')
            pending = (cp, name[:-8], category)
            continue
        start = cp
        if name.endswith(', Last>'):
            if not pending or pending[1:] != (name[:-7], category):
                raise ValueError('unpaired Last range')
            start = pending[0]
            pending = None
        elif pending:
            raise ValueError('First range not followed by matching Last')
        if category == 'Cs':
            if not 0xD800 <= start <= cp <= 0xDFFF:
                raise ValueError('surrogate category outside surrogate range')
            excluded += cp - start + 1
            continue
        if start <= 0xDFFF and cp >= 0xD800:
            raise ValueError('non-surrogate category intersects surrogate range')
        counts[category] += cp - start + 1
        if ranges and ranges[-1][1] + 1 == start and ranges[-1][2] == category:
            ranges[-1][1] = cp
        else:
            ranges.append([start, cp, category])
    if pending:
        raise ValueError('unterminated First range')
    return {'ranges': ranges, 'counts': dict(sorted(counts.items())),
            'assigned_scalars': sum(counts.values()), 'excluded_non_scalars': excluded}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, required=True, help='pinned UnicodeData.txt')
    parser.add_argument('--out', type=Path, default=ROOT / 'tests/vt/assigned-ranges.json')
    args = parser.parse_args()
    pins = json.loads((ROOT / 'tests/vt/unicode-sources.json').read_text())
    source = next(item for item in pins['sources'] if item['name'] == 'UnicodeData.txt')
    data = args.data.read_bytes()
    if hashlib.sha256(data).hexdigest() != source['sha256']:
        parser.error('UnicodeData digest does not match the normative pin')
    result = {'schema': 1, 'version': pins['version'], 'source_sha256': source['sha256'], **assigned(data)}
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print('ASSIGNED scalars=%d excluded-non-scalars=%d ranges=%d' %
          (result['assigned_scalars'], result['excluded_non_scalars'], len(result['ranges'])))


if __name__ == '__main__':
    main()
