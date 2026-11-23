#!/usr/bin/env python3
"""toml-table-oracle: tests/config/toml.table held against Python's tomllib (TOML 1.0), the TOML oracle.

Each case is a file's text and what warren's TOML subset makes of it: a reading (`=` lines) or a refusal
(`! LINE REASON`). warren's side of the table is src/toml_table_test.lu. This checks each case's category:

- accepted: tomllib reads the text, and its reading, written by the table's rule, is the case's `=` lines;
- not-toml: tomllib refuses the text, at the case's line, or at the line `tomllib-line=N` names where the two
  report different lines;
- outside: tomllib reads the text: valid TOML, outside warren's subset, the form named by warren's reason.

The counts of each category are held, so a case that goes missing is seen.

  toml_table.py [TABLE]
"""
import re
import sys
import tomllib
from pathlib import Path

COUNTS = {'accepted': 40, 'not-toml': 55, 'outside': 30}
LINE = re.compile(r'\(at line (\d+), column \d+\)')


def expand(text):
    """A document line's text: {tab} a tab, {cr} a carriage return, {u+HEX} that scalar; any other { as written."""
    out, i = [], 0
    while i < len(text):
        if text[i] == '{':
            j = text.find('}', i)
            token = text[i + 1:j] if j > 0 else ''
            if token == 'tab':
                out.append('\t')
                i = j + 1
                continue
            if token == 'cr':
                out.append('\r')
                i = j + 1
                continue
            if re.fullmatch(r'u\+[0-9A-Fa-f]{1,6}', token):
                out.append(chr(int(token[2:], 16)))
                i = j + 1
                continue
        out.append(text[i])
        i += 1
    return ''.join(out)


def quote(s):
    """A string as the reading writes it: in double quotes, `"` and `\\` escaped, controls as \\u00XX."""
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == '\\':
            out.append('\\\\')
        elif o < 0x20 or o == 0x7f:
            out.append('\\u%04X' % o)
        else:
            out.append(ch)
    out.append('"')
    return ''.join(out)


def reading(doc):
    """One line a value, PATH = VALUE, sorted: an array of tables' elements as PATH[N], an empty table as {}."""
    lines = []

    def walk(path, value):
        if isinstance(value, dict):
            if not value and path:
                lines.append(path + ' = {}')
            for key, item in value.items():
                walk(path + '.' + key if path else key, item)
        elif isinstance(value, list) and value and all(isinstance(x, dict) for x in value):
            for n, item in enumerate(value):
                walk('%s[%d]' % (path, n), item)
        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
            lines.append(path + ' = [' + ', '.join(quote(x) for x in value) + ']')
        elif isinstance(value, bool):
            lines.append(path + (' = true' if value else ' = false'))
        elif isinstance(value, int):
            lines.append('%s = %d' % (path, value))
        elif isinstance(value, str):
            lines.append(path + ' = ' + quote(value))
        else:
            lines.append('%s = <%s>' % (path, type(value).__name__))

    walk('', doc)
    return sorted(lines)


class Case:
    def __init__(self, name, category, flags, at):
        self.name, self.category, self.flags, self.at = name, category, flags, at
        self.lines, self.reading, self.refusal = [], [], None

    def text(self):
        if not self.lines:
            return ''
        return '\n'.join(self.lines) + ('' if 'noeol' in self.flags else '\n')


def cases(path):
    out, case = [], None
    for n, line in enumerate(path.read_text(encoding='utf-8').split('\n'), 1):
        if line.startswith('case '):
            words = line.split(' ')
            if len(words) < 3 or words[2] not in COUNTS:
                raise ValueError('line %d: a case line is `case NAME CATEGORY [FLAG...]`' % n)
            case = Case(words[1], words[2], words[3:], n)
            out.append(case)
        elif line == '>' or line.startswith('> '):
            if case is None:
                raise ValueError('line %d: a document line outside a case' % n)
            case.lines.append(expand(line[2:]))
        elif line.startswith('= '):
            if case is None:
                raise ValueError('line %d: a reading line outside a case' % n)
            case.reading.append(line[2:])
        elif line.startswith('! '):
            if case is None or case.refusal is not None:
                raise ValueError('line %d: a second refusal, or one outside a case' % n)
            words = line[2:].split(' ', 1)
            case.refusal = (int(words[0]), words[1] if len(words) > 1 else '')
        elif line and not line.startswith('#'):
            raise ValueError('line %d: not a case, document, reading, refusal or comment line' % n)
    return out


def tomllib_line(case):
    for flag in case.flags:
        if flag.startswith('tomllib-line='):
            return int(flag.split('=', 1)[1])
    return case.refusal[0]


def check(case):
    """'' when tomllib agrees with the case, else why not."""
    for flag in case.flags:
        if flag != 'noeol' and not flag.startswith('tomllib-line='):
            return 'unknown flag %s' % flag
    text = case.text()
    try:
        doc = tomllib.loads(text)
        error = None
    except tomllib.TOMLDecodeError as e:
        doc, error = None, str(e)
    if case.category == 'accepted':
        if case.refusal is not None:
            return 'an accepted case holds a refusal'
        if error is not None:
            return 'tomllib refused it: %s' % error
        got = reading(doc)
        if got != case.reading:
            return 'tomllib reads %r, the table %r' % (got, case.reading)
        return ''
    if case.refusal is None or case.reading:
        return 'a refused case needs one refusal and no reading'
    if case.category == 'outside':
        if error is not None:
            return 'tomllib refused it (%s): it is not valid TOML' % error
        return ''
    if error is None:
        return 'tomllib read it: %r' % reading(doc)
    m = LINE.search(error)
    line = int(m.group(1)) if m else text.replace('\r\n', '\n').count('\n') + 1
    if line != tomllib_line(case):
        return 'tomllib refused it at line %d (%s), the table says %d' % (line, error, tomllib_line(case))
    return ''


def main(argv):
    path = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent / 'toml.table'
    try:
        table = cases(path)
    except (OSError, ValueError) as e:
        print('FAIL toml-table-oracle %s' % e)
        return 1
    failed, seen, names = 0, {k: 0 for k in COUNTS}, set()
    for case in table:
        why = 'the name is given twice' if case.name in names else check(case)
        names.add(case.name)
        seen[case.category] += 1
        if why:
            failed += 1
            print('FAIL toml-table-oracle %s: %s' % (case.name, why))
    for category, want in COUNTS.items():
        if seen[category] != want:
            failed += 1
            print('FAIL toml-table-oracle %d %s cases, not %d' % (seen[category], category, want))
    if failed:
        print('TOML-TABLE-ORACLE cases=%d failed=%d' % (len(table), failed))
        return 1
    print('PASS toml-table-oracle cases=%d %s python=%s' % (
        len(table), ' '.join('%s=%d' % kv for kv in seen.items()), sys.version.split()[0]))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
