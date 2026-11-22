#!/usr/bin/env python3
"""send-keys-table-equal: tests/session/send-keys.table, the bytes a pane reads for each send-keys case in
three modes, tmux 3.4's column measured and warren's column held by src/send_keys_table_test.lu. Every row
named `-` has equal columns, and every other row names one of the differences docs/CLI.md and the README give.

  send_keys_table.py [TABLE]
"""
import sys
from pathlib import Path

NAMED = {'home-end-as-typed': 9, 'keypad-enter-cr-as-typed': 2, 'ctrl-without-a-byte': 21}


def main():
    path = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent / 'send-keys.table')
    fails, equal, named = [], 0, {}
    for number, line in enumerate(path.read_text(encoding='utf-8').splitlines(), 1):
        if not line or line.startswith('#'):
            continue
        mode, args, tmux, warren, why = line.split('\t')
        if mode not in ('normal', 'cursor', 'keypad'):
            fails.append('line %d: mode %r' % (number, mode))
        if why == '-':
            equal += 1
            if tmux != warren:
                fails.append('line %d: %s %s unnamed but tmux %s, warren %s' % (number, mode, args, tmux, warren))
        elif why in NAMED:
            named[why] = named.get(why, 0) + 1
            if tmux == warren:
                fails.append('line %d: %s %s named %s but equal' % (number, mode, args, why))
        else:
            fails.append('line %d: unknown difference %r' % (number, why))
    if equal != 359 or named != NAMED:
        fails.append('equal rows %d (359), named %s (%s)' % (equal, named, NAMED))
    for f in fails:
        print('FAIL send-keys-table-equal ' + f)
    if not fails:
        print('PASS send-keys-table-equal equal=%d named=%s' % (equal, ' '.join('%s=%d' % kv for kv in sorted(named.items()))))
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
