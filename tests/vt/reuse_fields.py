#!/usr/bin/env python3
"""reuse-fields: every field of a pane slot is named with what a reuse does to it.

A pane slot is reused, never dropped. This census reads the declarations of `Pane` (src/server/session.lu) and
`Vt` (src/vt/grid.lu) and holds them to tests/vt/reuse-fields.table, one line per field:

  STRUCT FIELD reset CHAIN       the field is set or cleared on the reuse path, at the end of CHAIN
  STRUCT FIELD kept -- WHY       the field keeps its value, and why that is right
  STRUCT FIELD counter -- WHY    the field only grows, and why nothing reads it as the last program's

CHAIN is `f1>f2>...>fn`, or an `alias NAME CHAIN` defined in the table and written `@NAME`. It holds when f1 calls
f2, f2 calls f3, and so on, and fn's body names the field as `.FIELD`. Each chain starts at a function on the
reuse path: `reuse` (vt.reuse), `acquire_pane`, which reuses the slot through `fresh_screen`, or `spawn_pane_in`.

A field added to either struct and not in the table fails here by name, until a line says what a reuse does to it.
The behaviour itself is held by src/vt_reuse_test.lu (a reused pane against a new one) and by the session rows.

  reuse_fields.py [ROOT]
"""
import re
import sys
from pathlib import Path

STRUCTS = {'Pane': 'src/server/session.lu', 'Vt': 'src/vt/grid.lu'}
HEADS = {'reuse', 'acquire_pane', 'spawn_pane_in'}


def strip(text):
    """The text with string literals and comments blanked, so that braces in them are not counted."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c == '"':
            out.append('"')
            i += 1
            while i < n and text[i] != '"':
                if text[i] == '\\':
                    i += 1
                out.append(' ' if text[i] != '\n' else '\n')
                i += 1
            out.append('"')
            i += 1
        elif text.startswith('//', i):
            while i < n and text[i] != '\n':
                out.append(' ')
                i += 1
        else:
            out.append(c)
            i += 1
    return ''.join(out)


def block(text, start):
    """The text from the `{` at or after `start` to its matching `}`."""
    open_at = text.index('{', start)
    depth = 0
    for i in range(open_at, len(text)):
        if text[i] == '{':
            depth += 1
        elif text[i] == '}':
            depth -= 1
            if depth == 0:
                return text[open_at:i + 1]
    raise ValueError('unbalanced braces')


def struct_fields(root, name, path):
    text = strip((root / path).read_text())
    m = re.search(r'\bpub struct ' + name + r'\s*\{', text)
    if not m:
        raise ValueError('no struct %s in %s' % (name, path))
    body = block(text, m.start())[1:-1]
    fields, depth, cur = [], 0, ''
    for c in body:
        if c in '[(':
            depth += 1
        elif c in '])':
            depth -= 1
        if depth == 0 and c in ',\n':
            cur = cur.strip()
            if cur:
                fields.append(cur.split(':')[0].strip())
            cur = ''
        else:
            cur += c
    if cur.strip():
        fields.append(cur.strip().split(':')[0].strip())
    return fields


class Functions:
    def __init__(self, root):
        self.defs = {}
        for path in sorted((root / 'src').rglob('*.lu')):
            text = strip(path.read_text())
            for m in re.finditer(r'(?m)^(?:pub )?fn (\w+)\s*(?:\[[^\]]*\])?\(', text):
                # The body's `{` is the last character of the signature's last line.
                end = re.compile(r'\{[ \t]*$', re.M).search(text, m.end())
                if not end:
                    continue
                self.defs.setdefault(m.group(1), []).append((path.parent, block(text, end.start())))

    def body(self, name, near):
        found = self.defs.get(name, [])
        if not found:
            raise ValueError('no function %s' % name)
        same = [b for d, b in found if d == near]
        if len(same) == 1:
            return same[0], near
        if len(found) == 1:
            return found[0][1], found[0][0]
        raise ValueError('function %s is defined more than once' % name)


def check_chain(funcs, chain, field, home):
    names = chain.split('>')
    if names[0] not in HEADS:
        return 'the chain starts at %s, which is not on the reuse path (%s)' % (names[0], ', '.join(sorted(HEADS)))
    near = home
    for here, there in zip(names, names[1:]):
        body, near = funcs.body(here, near)
        if not re.search(r'\b' + there + r'\(', body):
            return '%s does not call %s' % (here, there)
        near = funcs.body(there, near)[1]
    body, _ = funcs.body(names[-1], near)
    if not re.search(r'\.' + field + r'\b', body):
        return '%s does not name .%s' % (names[-1], field)
    return ''


def main(argv):
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parents[2]
    table = (root / 'tests/vt/reuse-fields.table').read_text().split('\n')
    aliases, claims, failed = {}, {}, 0
    for n, line in enumerate(table, 1):
        if not line.strip() or line.startswith('#'):
            continue
        words = line.split()
        if words[0] == 'alias' and len(words) == 3:
            aliases[words[1]] = words[2]
            continue
        if len(words) < 3 or words[0] not in STRUCTS or words[2] not in ('reset', 'kept', 'counter'):
            print('FAIL reuse-fields table line %d: %r' % (n, line))
            failed += 1
            continue
        key = (words[0], words[1])
        if key in claims:
            print('FAIL reuse-fields %s.%s is named twice' % key)
            failed += 1
        if words[2] == 'reset':
            if len(words) != 4:
                print('FAIL reuse-fields table line %d: reset needs one chain' % n)
                failed += 1
                continue
            chain = words[3]
            if chain.startswith('@'):
                parts = chain[1:].split('>', 1)
                chain = aliases.get(parts[0], '?') + ('>' + parts[1] if len(parts) > 1 else '')
            claims[key] = ('reset', chain)
        else:
            if '--' not in words or words.index('--') != 3 or len(words) < 5:
                print('FAIL reuse-fields table line %d: %s needs `-- WHY`' % (n, words[2]))
                failed += 1
                continue
            claims[key] = (words[2], '')
    funcs = Functions(root)
    counts = {}
    for struct, path in STRUCTS.items():
        fields = struct_fields(root, struct, path)
        counts[struct] = len(fields)
        for field in fields:
            claim = claims.pop((struct, field), None)
            if claim is None:
                print('FAIL reuse-fields %s.%s is not in the table: say what a reuse does to it' % (struct, field))
                failed += 1
                continue
            if claim[0] == 'reset':
                try:
                    why = check_chain(funcs, claim[1], field, (root / path).parent)
                except ValueError as e:
                    why = str(e)
                if why:
                    print('FAIL reuse-fields %s.%s: %s' % (struct, field, why))
                    failed += 1
    for struct, field in sorted(claims):
        print('FAIL reuse-fields %s.%s is in the table but not in the struct' % (struct, field))
        failed += 1
    if failed:
        print('REUSE-FIELDS failed=%d' % failed)
        return 1
    print('PASS reuse-fields ' + ' '.join('%s=%d' % kv for kv in counts.items()))
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
