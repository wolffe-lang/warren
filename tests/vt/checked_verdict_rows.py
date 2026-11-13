#!/usr/bin/env python3
"""A conform-run process exit zero is not a successful checked verdict."""
from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[2]
validate = runpy.run_path(str(ROOT / 'tests/vt/checked_rows.py'))['validate']


def main():
    pin = {'version': '0.2.39', 'rev': '3fc86f77795afbbd6fbe483fef76c08e7f13a840'}
    good = {'protocol': 1, 'impl': 'wolfgang', 'impl_version': pin['version'], 'commit': '3fc86f7',
            'verdict': 'exit(0)', 'phase_reached': 'run', 'diagnostics': [], 'warnings': []}
    validate(good, pin)
    for change in ({'verdict': 'trap(assert)'}, {'verdict': 'fail(W0313)'}, {'verdict': 'unsupported'}, {'verdict': 'exit(7)'}, {'verdict': 'unknown'},
                   {'phase_reached': 'typecheck'}, {'impl_version': 'other'}, {'commit': ''},
                   {'commit': 'deadbee'}, {'warnings': ['W0313']}, {'diagnostics': ['E0301']}):
        try:
            validate({**good, **change}, pin)
        except ValueError:
            pass
        else:
            raise AssertionError('non-success checked record accepted: %r' % change)
    print('PASS checked-verdict rejects-traps-failures-unknown-phase-pin-warnings')


if __name__ == '__main__':
    main()
