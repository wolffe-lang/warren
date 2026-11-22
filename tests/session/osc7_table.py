#!/usr/bin/env python3
"""osc7-table-equal: tests/session/osc7.table, the path a pane keeps after each OSC 7 case, tmux 3.4's column
measured (held by tools/session/tmux_rows.py's tmux-osc7) and warren's held by src/osc7_table_test.lu. Every row
named `-` has equal columns. A `path-not-url` row's warren column is its tmux column, the URL tmux kept, decoded by
warren's rule (docs/TERM.md), which this checker applies. Every other named row ends with a report warren refuses
where tmux took it, and the checker holds the name to the report: other-host-ignored names a host that is not
empty, `localhost` or the machine's; over-long-dropped is past an OSC string's 4096 bytes; refuses-malformed is a
report warren's rule refuses as it was sent.

  osc7_table.py [TABLE]
"""
import sys
from pathlib import Path

NAMED = {'path-not-url': 20, 'refuses-malformed': 12, 'other-host-ignored': 2, 'over-long-dropped': 2}
EQUAL = 4
HOST = b'warren-table-host'


def expand(column):
    """A column's bytes: hex, {host} the stand-in name, {hh*N} byte hh N times."""
    out, i = bytearray(), 0
    while i < len(column):
        if column[i] == '{':
            j = column.index('}', i)
            token = column[i + 1:j]
            if token == 'host':
                out += HOST
            else:
                pair, n = token.split('*')
                out += bytes.fromhex(pair) * int(n)
            i = j + 1
        else:
            out += bytes.fromhex(column[i:i + 2])
            i += 2
    return bytes(out)


def decoded(url):
    """warren's reading of a report (docs/TERM.md): the path, or None when it is refused."""
    if url[:7].lower() != b'file://':
        return None
    rest = url[7:]
    slash = rest.find(b'/')
    if slash < 0 or rest[:slash].lower() not in (b'', b'localhost', HOST):
        return None
    out, i, path = bytearray(), 0, rest[slash:]
    while i < len(path):
        b = path[i]
        if b < 0x20 or b == 0x7f:
            return None
        if b == 0x25:
            pair = path[i + 1:i + 3]
            if len(pair) != 2 or any(c not in b'0123456789abcdefABCDEF' for c in pair):
                return None
            out.append(int(pair, 16))
            i += 3
        else:
            out.append(b)
            i += 1
    try:
        text = bytes(out).decode('utf-8')
    except UnicodeDecodeError:
        return None
    if '\0' in text or '�' in text:
        return None
    return bytes(out)


def last_report(payload):
    """The body (after `7;`) of the case's last OSC 7."""
    at = payload.rfind(b'\x1b]7;')
    if at < 0:
        return None
    body = payload[at + 4:]
    for end in (b'\x07', b'\x1b\\'):
        k = body.find(end)
        if k >= 0:
            body = body[:k]
    return body


def refusal_holds(why, payload, tmux):
    body = last_report(expand(payload))
    if body is None or tmux in ('kept', 'none'):
        return False
    if why == 'over-long-dropped':
        return len(b'7;') + len(body) > 4096
    if why == 'other-host-ignored':
        rest = body[7:]
        host = rest[:rest.find(b'/')] if b'/' in rest else rest
        return body[:7].lower() == b'file://' and host.lower() not in (b'', b'localhost', HOST)
    return decoded(body) is None


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'osc7.table')
    fails, equal, named = [], 0, {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        case, payload, tmux, warren, why = line.split('\t')
        if why == '-':
            equal += 1
            if tmux != warren:
                fails.append('line %d: %s unnamed but tmux %s, warren %s' % (number, case, tmux, warren))
        elif why == 'path-not-url':
            named[why] = named.get(why, 0) + 1
            if tmux in ('kept', 'none') or warren in ('kept', 'none'):
                fails.append('line %d: %s named path-not-url without two paths' % (number, case))
            elif decoded(expand(tmux)) != expand(warren):
                fails.append('line %d: %s: tmux %s decodes to %r, not warren %s' % (
                    number, case, tmux, decoded(expand(tmux)), warren))
        elif why in NAMED:
            named[why] = named.get(why, 0) + 1
            if tmux == warren or not refusal_holds(why, payload, tmux):
                fails.append('line %d: %s named %s but warren %s, tmux %s' % (number, case, why, warren, tmux))
        else:
            fails.append('line %d: unknown difference %r' % (number, why))
    if equal != EQUAL or named != NAMED:
        fails.append('equal rows %d (%d), named %s (%s)' % (equal, EQUAL, named, NAMED))
    for f in fails:
        print('FAIL osc7-table-equal ' + f)
    if not fails:
        print('PASS osc7-table-equal equal=%d named=%s' % (equal, ' '.join('%s=%d' % kv for kv in sorted(named.items()))))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
