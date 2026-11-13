#!/usr/bin/env python3
"""Prepare the pure VT build version from the package's single version field.

The generated member is an ignored build artifact. No run-time filesystem
access and no second hand-maintained version string enter the emulator.
"""
import argparse
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]


def package_version(root):
    text = (root / 'src/wolf.pkg').read_text()
    text = re.sub(r'//[^\n]*', '', text)
    fields = list(re.finditer(r'\bversion\s*:', text))
    if len(fields) != 1:
        raise SystemExit('FAIL package-version-field-count')
    value = re.match(r'\s*"([0-9]+\.[0-9]+\.[0-9]+(?:[-+][A-Za-z0-9.-]+)?)"\s*[,}]', text[fields[0].end():])
    if value is None:
        raise SystemExit('FAIL package-version-format')
    return value[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    args = parser.parse_args()
    version = package_version(args.root)
    text = ('//! member: true\n'
            '//! Generated at build preparation from src/wolf.pkg; do not edit.\n'
            '/// The package version used for this build, from its sole manifest field.\n'
            'pub fn package_version() -> str { "%s" }\n' % version)
    (args.root / 'src/vt/build_version.lu').write_text(text)
    print('PASS version-generation package=%s' % version)


if __name__ == '__main__':
    main()
