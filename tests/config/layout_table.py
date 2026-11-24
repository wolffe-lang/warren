#!/usr/bin/env python3
"""layout-table-oracle: tests/config/layout.table held against Python's tomllib (TOML 1.0).

Each case is a layout file's text and the line and reason warren's layout reader refuses it at; warren's side of
the table is src/layout_table_test.lu. Every case is a schema refusal, so every text must be valid TOML: this
checks that tomllib reads each one, that each case has one refusal line naming a line of its text (or line 1 of
an empty one), and that the table holds its count of cases, so one that goes missing is seen.

  layout_table.py [TABLE]
"""
import re
import sys
import tomllib
from pathlib import Path

CASES = 46
REFUSAL = re.compile(r'^(\d+) \S')


def cases(path):
    out, case = [], None
    for raw in path.read_text(encoding='utf-8').split('\n'):
        if raw.startswith('case '):
            case = {'name': raw[5:].strip(), 'lines': [], 'refusals': []}
            out.append(case)
        elif case is not None and (raw == '>' or raw.startswith('> ')):
            case['lines'].append(raw[2:])
        elif case is not None and raw.startswith('! '):
            case['refusals'].append(raw[2:])
    return out


def check(case):
    """Why the case fails the oracle, or None."""
    text = '\n'.join(case['lines']) + ('\n' if case['lines'] else '')
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        return 'tomllib refuses the text: %s' % e
    if len(case['refusals']) != 1:
        return '%d refusal lines, not 1' % len(case['refusals'])
    m = REFUSAL.match(case['refusals'][0])
    if not m:
        return 'the refusal %r names no line and reason' % case['refusals'][0]
    line = int(m.group(1))
    if line < 1 or line > max(1, len(case['lines'])):
        return 'the refusal names line %d of a %d-line text' % (line, len(case['lines']))
    return None


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent / 'layout.table'
    table = cases(path)
    failed, names = 0, set()
    for case in table:
        why = check(case)
        if case['name'] in names:
            why = 'the name is used twice'
        names.add(case['name'])
        if why:
            failed += 1
            print('FAIL layout-table-oracle %s: %s' % (case['name'], why))
    if len(table) != CASES:
        failed += 1
        print('FAIL layout-table-oracle %d cases, not %d' % (len(table), CASES))
    if failed:
        print('LAYOUT-TABLE-ORACLE cases=%d failed=%d' % (len(table), failed))
        return 1
    print('PASS layout-table-oracle cases=%d python=%s' % (len(table), sys.version.split()[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
