#!/usr/bin/env python3
"""D9 reference fixture changes are bounded by exact cells, fields and values."""
import copy
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
MODULE = runpy.run_path(str(ROOT / 'tests/vt/d9_fixture.py'))


def main():
    verify, one_x = MODULE['verify_background_delta'], MODULE['one_x']
    original = one_x('bg=idx:181')
    repaired = one_x('-')
    verify(original, repaired, {(1, 1)}, None)
    assert original == one_x('bg=idx:181')
    verify(repaired, repaired, set(), None)
    changes = []
    bad = copy.deepcopy(repaired); bad['rows'][0][1][2] = 'bg=idx:2'; changes.append(bad)
    bad = copy.deepcopy(repaired); bad['rows'][0][0][2] = 'fg=idx:3'; changes.append(bad)
    bad = copy.deepcopy(repaired); bad['rows'][1][0][1] = 'U+0041'; changes.append(bad)
    bad = copy.deepcopy(repaired); bad['cursor']['col'] = 3; changes.append(bad)
    bad = copy.deepcopy(repaired); bad['rows'][0][0][2] = 'bg=idx:2'; changes.append(bad)
    changes.append(original)
    for bad in changes:
        try:
            verify(original, bad, {(1, 1)}, None)
        except AssertionError:
            pass
        else:
            raise AssertionError('D9 repair changed an unapproved cell/field/value')
    definitions = MODULE['definitions']()
    assert len(definitions) == 37 and sum(entry['pen_status'] for entry in definitions.values()) == 22
    print('PASS D9 bounds exact-cells background-only exact-value outside-cell glyph cursor no-mutation')


if __name__ == '__main__':
    main()
