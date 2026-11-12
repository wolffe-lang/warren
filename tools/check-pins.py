#!/usr/bin/env python3
"""Check pin metadata consistency before downloading or executing anything."""
import hashlib
import json
from pathlib import Path
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def main():
    pins = tomllib.loads((ROOT / 'wolf-toolchain.toml').read_text())
    first = json.loads((ROOT / 'tests/pin-read-1.json').read_text())
    second = json.loads((ROOT / 'tests/pin-read-2.json').read_text())
    if first != second:
        raise ValueError('independent release metadata reads differ')
    for name in ('wolf', 'lupin'):
        pin = pins[name]
        if first[name]['tag'] != 'v' + pin['version'] or first[name]['commit'] != pin['rev']:
            raise ValueError('release tag or commit mismatch: ' + name)
        assets = {a['name']: a for a in first[name]['assets']}
        for target in ('aarch64-apple-darwin', 'x86_64-unknown-linux-gnu', 'aarch64-unknown-linux-gnu'):
            asset = assets[f'{name}-{pin["version"]}-{target}.tar.gz']
            if asset['digest'] != 'sha256:' + pin[target]:
                raise ValueError('archive pin differs from release: ' + name + '/' + target)
    if (first['std']['commit'], first['std']['tree']) != (pins['std']['rev'], pins['std']['tree']):
        raise ValueError('std pin differs from the commit read')
    count = 0
    oracle_file = ROOT / 'warren-oracle.toml'
    if oracle_file.exists():
        oracle = tomllib.loads(oracle_file.read_text())
        for file, key in [('ci/packages.txt', 'packages_sha256'),
                          ('ci/oracle-binaries.lock', 'binary_manifest_sha256')]:
            if hashlib.sha256((ROOT / file).read_bytes()).hexdigest() != oracle['container'][key]:
                raise ValueError('oracle metadata digest mismatch: ' + file)
        recipe = (ROOT / 'ci/oracle.Containerfile').read_text()
        if 'FROM ' + oracle['container']['base'] + '\n' not in recipe:
            raise ValueError('container base differs from pin')
        if 'ARG SNAPSHOT=' + oracle['container']['snapshot'] + '\n' not in recipe:
            raise ValueError('package snapshot differs from pin')
        manifest = (ROOT / 'ci/oracle-binaries.lock').read_text()
        for name in ('xterm', 'tmux', 'xvfb', 'infocmp'):
            if oracle[name]['sha256'] not in manifest:
                raise ValueError('binary manifest omits ' + name)
            count += 1
    print('PASS pin-metadata toolchains=2 std=1 oracle_binaries=%d' % count)


if __name__ == '__main__':
    main()
