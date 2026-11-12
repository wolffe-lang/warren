#!/usr/bin/env python3
"""A checked observation's command exit is not its program verdict."""
import json
from pathlib import Path
import sys

record = json.loads(Path(sys.argv[1]).read_text())
assert record['impl'] == 'wolfgang', record
assert record['phase_reached'] == 'run', record
assert record['verdict'] == 'exit(0)', record
assert not record['diagnostics'] and not record['warnings'], record
text = record['stdout_inline']
for name in ('proto-version-before-versioned-suffix',
             'proto-golden-and-named-refusals',
             'proto-wide-boundary-and-full-coverage',
             'proto-fragment-all-splits-and-stale-ack-after-reset',
             'proto-golden-all-21-types'):
    assert 'PASS ' + name + '\n' in text, (name, record)
print(text, end='')
print('PASS proto-checked-observation verdict=exit(0)')
