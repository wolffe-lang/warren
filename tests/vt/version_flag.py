#!/usr/bin/env python3
"""`warren --version` prints the package manifest's version, and no source
carries a second copy of it.

  tests/vt/version_flag.py BINARY      run BINARY --version against src/wolf.pkg
  tests/vt/version_flag.py --self-test the row's own plants
"""
from pathlib import Path
import os
import re
import stat
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
LITERAL = re.compile(r'"warren [0-9]+\.[0-9]+\.[0-9]+')


def manifest_version(root):
    text = re.sub(r'//[^\n]*', '', (root / 'src/wolf.pkg').read_text())
    fields = re.findall(r'\bversion\s*:\s*"([^"]*)"', text)
    assert len(fields) == 1, 'version-manifest-field-count %d' % len(fields)
    return fields[0]


def no_second_literal(root):
    for path in sorted((root / 'src').rglob('*.lu')):
        if path.name.endswith('_test.lu') or path.name == 'build_version.lu':
            continue
        assert not LITERAL.search(path.read_text()), 'version-second-literal %s' % path.relative_to(root)


def check(root, binary):
    version = manifest_version(root)
    no_second_literal(root)
    assert Path(binary).is_file(), 'version-binary-missing %s' % binary
    out = subprocess.run([binary, '--version'], capture_output=True, text=True, timeout=60)
    want = 'warren %s\n' % version
    assert out.returncode == 0 and out.stdout == want, \
        'version-flag-disagrees manifest=%s status=%d printed=%r' % (version, out.returncode, out.stdout)
    print('PASS version-flag %s' % version)


def self_test():
    with tempfile.TemporaryDirectory() as t:
        base = Path(t)
        (base / 'src').mkdir()
        (base / 'src/wolf.pkg').write_text('pkg { name: "warren", version: "1.2.3", edition: "1" }\n')
        (base / 'src/a.lu').write_text('fn f() {}\n')

        def fake(printed, status=0):
            exe = base / 'fake'
            exe.write_text('#!/bin/sh\nprintf "%s\\n" "' + printed + '"\nexit ' + str(status) + '\n')
            exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
            return str(exe)

        check(base, fake('warren 1.2.3'))
        for printed, status, why in (('warren 1.2.4', 0, 'disagrees'), ('warren 1.2.3', 2, 'disagrees'), ('1.2.3', 0, 'disagrees')):
            try:
                check(base, fake(printed, status))
            except AssertionError as e:
                assert why in str(e), e
            else:
                raise AssertionError('not refused: %s %d' % (printed, status))
        (base / 'src/a.lu').write_text('fn f() { print("warren 1.2.3") }\n')
        try:
            check(base, fake('warren 1.2.3'))
        except AssertionError as e:
            assert 'version-second-literal' in str(e), e
        else:
            raise AssertionError('second literal not refused')
    print('PASS version-flag-self-test agree disagree status bare second-literal')


def main():
    if sys.argv[1:] == ['--self-test']:
        self_test()
    elif len(sys.argv) == 2:
        try:
            check(ROOT, sys.argv[1])
        except AssertionError as e:
            print('FAIL ' + str(e))
            raise SystemExit(1)
    else:
        raise SystemExit('usage: version_flag.py BINARY | --self-test')


if __name__ == '__main__':
    main()
