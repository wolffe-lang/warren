#!/usr/bin/env python3
"""Hold the assigned-scalar sweep to D11's exact 350 ruled differences."""
from bisect import bisect_right
from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def expected_differences():
    policy = json.loads((ROOT / 'tests/vt/width-divergences.json').read_text())
    assert policy['schema'] == 1 and policy['divergence'] == 'D11' and policy['total'] == 350
    ranges = json.loads((ROOT / 'tests/vt/assigned-ranges.json').read_text())['ranges']
    starts = [entry[0] for entry in ranges]
    expected = []
    for group in policy['groups']:
        count = 0
        for low, high in group['ranges']:
            for cp in range(int(low, 16), int(high, 16) + 1):
                first, last, category = ranges[bisect_right(starts, cp) - 1]
                assert first <= cp <= last
                assert group['category'] is None or category == group['category']
                expected.append({'scalar': 'U+%04X' % cp, 'category': category,
                    'expected': group['native'], 'row': 1, 'col': group['reference'] + 2,
                    'classification': 'native-%d-reference-%d' % (group['native'], group['reference'])})
                count += 1
        assert count == group['count']
    assert len(expected) == 350 and len({entry['scalar'] for entry in expected}) == 350
    return sorted(expected, key=lambda entry: int(entry['scalar'][2:], 16))


def validate(result):
    policy = json.loads((ROOT / 'tests/vt/width-divergences.json').read_text())
    assert result['unicode'] == policy['unicode'], ('width Unicode version', result['unicode'])
    assert result['measured_scalars'] == policy['assigned_scalars'] == 287346
    assert result['excluded_non_scalars'] == 2048
    for field, filename in (('assigned_sha256', 'assigned-ranges.json'), ('widths_sha256', 'width-ranges.json')):
        assert result[field] == hashlib.sha256((ROOT / 'tests/vt' / filename).read_bytes()).hexdigest()
    controls = result['controls']
    assert len(controls) == 65
    assert {entry['scalar'] for entry in controls} == {'U+%04X' % cp for cp in [*range(32), *range(127, 160)]}
    assert all(entry['category'] == 'Cc' and entry['classification'] == 'control' for entry in controls)
    expected = expected_differences()
    actual = sorted(result['disagreements'], key=lambda entry: int(entry['scalar'][2:], 16))
    assert actual == expected, 'D11 changed: a missing, additional or different scalar-width result is red'
    classes = Counter(entry['classification'] for entry in expected)
    classes.update({'control': 65, 'equal': 286931})
    assert result['classifications'] == dict(classes)
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('result', type=Path)
    args = parser.parse_args()
    path = args.result / 'result.json' if args.result.is_dir() else args.result
    result = json.loads(path.read_text())
    validate(result)
    for filename in ('measurements.tsv', 'replies.bin'):
        assert hashlib.sha256((path.parent / filename).read_bytes()).hexdigest() == result[filename + '_sha256']
    print('PASS width-policy D11 exact-differences=350 measured=287346 controls=65 any-351st-red')


if __name__ == '__main__':
    main()
