#!/usr/bin/env python3
"""Bind frozen reference screens to source inputs and existing oracle pins."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
from reference_inputs import inputs
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen

MANIFESTS = {'census': 'tests/vt/census.sha256',
             'recordings': 'tests/corpus/recording-screens.sha256',
             'fuzz-baseline': 'tests/corpus/fuzz-screens.sha256'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def build_index():
    result = {'schema': 1, 'capture_head': '2bb72fabbab74437e375fb8ee6c20d7b506157a6',
              'pins': {name: digest((ROOT / name).read_bytes()) for name in
                       ('warren-oracle.toml', 'ci/packages.txt', 'ci/oracle-binaries.lock')}, 'suites': {}}
    sources = inputs()
    for suite, manifest in MANIFESTS.items():
        entries = dict(line.split() for line in (ROOT / manifest).read_text().splitlines() if line)
        directory = ROOT / 'tests/vt/reference' / suite
        assert set(entries) == set(sources[suite])
        assert {path.stem for path in directory.glob('*.screen')} == set(entries)
        rows = {}
        for name, expected in sorted(entries.items()):
            path = directory / (name + '.screen')
            data = path.read_bytes()
            assert digest(data) == expected == digest(path.read_bytes()), name
            parsed = screen.loads(data.decode())
            assert screen.loads(screen.dumps(parsed)) == parsed
            raw, replay = sources[suite][name]
            rows[name] = {'input_sha256': digest(raw), 'screen_sha256': expected, 'replay': replay}
        result['suites'][suite] = rows
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--write-index', action='store_true')
    args = parser.parse_args()
    index = build_index()
    target = ROOT / 'tests/vt/reference/index.json'
    if args.write_index:
        target.write_text(json.dumps(index, indent=2) + '\n')
    else:
        assert json.loads(target.read_text()) == index
    print('PASS frozen-reference-bindings census=151 recordings=5 fuzz-baseline=32 input+screen+pins')


if __name__ == '__main__':
    main()
