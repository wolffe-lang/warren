#!/usr/bin/env python3
"""layout-files-tomllib: the layout files warren's round trip writes, held to Python's tomllib (TOML 1.0).

src/layout_file_rows.lu --sample DIR writes the round trip's first 512 files, each NAME.toml with NAME.reading,
warren's TOML reading of it (one line a value, sorted, as tests/config/toml.table writes readings). This reads
each file with tomllib, writes its reading by the same rule (toml_table.py's), and holds the two equal, so every
file warren writes is TOML that tomllib reads as warren does.

  layout_files.py DIR
"""
import importlib.util
import sys
import tomllib
from pathlib import Path

FILES = 512


def table_rules():
    """toml_table.py's reading rule, loaded from beside this file (python3 -I puts no directory on the path)."""
    path = Path(__file__).resolve().parent / 'toml_table.py'
    spec = importlib.util.spec_from_file_location('toml_table', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main(argv):
    if len(argv) != 2:
        print('FAIL layout-files-tomllib usage: layout_files.py DIR')
        return 2
    rules = table_rules()
    files = sorted(Path(argv[1]).glob('*.toml'))
    failed = 0
    for f in files:
        text = f.read_bytes().decode('utf-8')
        try:
            doc = tomllib.loads(text)
        except tomllib.TOMLDecodeError as e:
            failed += 1
            print('FAIL layout-files-tomllib %s: tomllib refuses it: %s' % (f.name, e))
            continue
        # Lines end at LF only: a reading may hold U+2028, which str.splitlines would break at.
        want = f.with_suffix('.reading').read_bytes().decode('utf-8').split('\n')
        if want and want[-1] == '':
            want.pop()
        got = rules.reading(doc)
        if got != want:
            failed += 1
            for i in range(max(len(got), len(want))):
                g = got[i] if i < len(got) else '(none)'
                w = want[i] if i < len(want) else '(none)'
                if g != w:
                    print('FAIL layout-files-tomllib %s: line %d tomllib %r, warren %r' % (f.name, i + 1, g, w))
                    break
    if len(files) != FILES:
        failed += 1
        print('FAIL layout-files-tomllib %d files, not %d' % (len(files), FILES))
    if failed:
        print('LAYOUT-FILES-TOMLLIB files=%d failed=%d' % (len(files), failed))
        return 1
    print('PASS layout-files-tomllib files=%d python=%s' % (len(files), sys.version.split()[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
