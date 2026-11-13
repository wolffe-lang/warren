#!/usr/bin/env python3
"""Run pure grid programs on the explicit checked machine, never native fallback."""
import argparse
import json
from pathlib import Path
import subprocess
import tomllib

ROOT = Path(__file__).resolve().parents[2]
ENTRIES = ('vt_grid_test', 'vt_unicode_test', 'vt_ops_test', 'vt_screen_state_test',
           'vt_graphics_test', 'vt_events_test', 'vt_dump_test', 'vt_width_test',
           'vt_history_test', 'vt_resize_test', 'vt_interaction_test')


def validate(record, pin):
    if record.get('protocol') != 1 or record.get('impl') != 'wolfgang':
        raise ValueError('not the expected observation protocol/implementation')
    commit = record.get('commit')
    if record.get('impl_version') != pin['version'] or not isinstance(commit, str) or not 7 <= len(commit) <= 40 or not pin['rev'].startswith(commit):
        raise ValueError('checked machine identity differs from the pin')
    if record.get('verdict') != 'exit(0)' or record.get('phase_reached') != 'run':
        raise ValueError('checked verdict=%r phase=%r' % (record.get('verdict'), record.get('phase_reached')))
    if record.get('diagnostics') or record.get('warnings'):
        raise ValueError('checked observation has diagnostics or warnings')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT / 'target/checked-vt')
    parser.add_argument('wolf')
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    pin = tomllib.loads((ROOT / 'wolf-toolchain.toml').read_text())['wolf']
    failed = 0
    for entry in ENTRIES:
        command = [args.wolf, 'conform-run', 'src/' + entry + '.lu', '--json', '--checked', '--deny-warnings']
        try:
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=300)
            (args.out / (entry + '.json')).write_bytes(result.stdout)
            (args.out / (entry + '.stderr')).write_bytes(result.stderr)
            if result.returncode:
                raise ValueError('observation command exit=%d' % result.returncode)
            validate(json.loads(result.stdout), pin)
        except (ValueError, OSError, subprocess.TimeoutExpired) as error:
            failed += 1
            print('FAIL checked-vt %s %s' % (entry, error), flush=True)
        else:
            print('PASS checked-vt %s explicit-conform-run-checked' % entry, flush=True)
    print('CHECKED-VT entries=%d failed=%d' % (len(ENTRIES), failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
