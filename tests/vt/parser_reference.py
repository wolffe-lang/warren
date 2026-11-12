#!/usr/bin/env python3
"""Check the extra parser reference fixtures without running an emulator.

These are black-box snapshots, not warren screen-agreement claims. The full
screen comparison comes when the grid exists. D8 deliberately keeps the
reference's title unchanged in its fixture; a candidate expects DEL dropped.
"""
import hashlib
import json
from pathlib import Path
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen  # noqa: E402


def main():
    base = ROOT / 'tests/vt/parser-reference'
    manifest = json.loads((base / 'manifest.json').read_text())
    pins = tomllib.loads((ROOT / 'warren-oracle.toml').read_text())
    assert manifest['xterm_sha256'] == pins['xterm']['sha256']
    assert manifest['packages_sha256'] == pins['container']['packages_sha256']
    names = set()
    for case in manifest['cases']:
        name = case['name']
        assert name not in names
        names.add(name)
        for suffix, key in [('.in', 'input_sha256'), ('.screen', 'screen_sha256')]:
            assert hashlib.sha256((base / (name + suffix)).read_bytes()).hexdigest() == case[key], name
        got = screen.loads((base / (name + '.screen')).read_text())
        assert got['size'] == case['size'], name
        assert screen.loads(screen.dumps(got)) == got, name
        if case['classification'] == 'D8':
            assert name == 'osc-del' and got['title'] == '613f62'
        else:
            assert case['classification'] == 'reference'
        if case['size'][1] == 1:
            assert got['region'] == [1, 1], name
        print('PASS parser-reference-fixture ' + name)
    assert {p.stem for p in base.glob('*.in')} == names
    assert {p.stem for p in base.glob('*.screen')} == names
    assert len(names) == 19
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (AssertionError, ValueError, KeyError) as error:
        print('FAIL parser-reference-fixtures ' + str(error))
        sys.exit(1)
