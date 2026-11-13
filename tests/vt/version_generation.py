#!/usr/bin/env python3
"""The package version is read at build preparation, never hand copied."""
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / 'tools/vt/generate_version.py'


def main():
    work = ROOT / 'target/version-rows'
    work.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work) as temporary:
        root = Path(temporary)
        (root / 'src/vt').mkdir(parents=True)
        for version in ('7.3.19', '7.3.20'):
            (root / 'src/wolf.pkg').write_text('pkg { name: "warren", version: "%s", edition: "1" }\n' % version)
            subprocess.run([sys.executable, '-I', str(GENERATOR), '--root', str(root)], check=True)
            generated = (root / 'src/vt/build_version.lu').read_text()
            assert 'pub fn package_version() -> str { "%s" }' % version in generated
            assert generated.count('7.3.') == 1
        (root / 'src/wolf.pkg').write_text('pkg { version: "1.0.0", version: "2.0.0" }\n')
        result = subprocess.run([sys.executable, '-I', str(GENERATOR), '--root', str(root)], capture_output=True)
        assert result.returncode != 0, 'version-duplicate-not-refused'
        assert '7.3.20' in (root / 'src/vt/build_version.lu').read_text()
        (root / 'src/wolf.pkg').write_text('pkg { version: "1.0.0\"; unsafe" }\n')
        result = subprocess.run([sys.executable, '-I', str(GENERATOR), '--root', str(root)], capture_output=True)
        assert result.returncode != 0, 'version-malformed-not-refused'
    print('PASS version-generation manifest-change duplicate malformed')


if __name__ == '__main__':
    main()
