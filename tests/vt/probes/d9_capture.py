#!/usr/bin/env python3
"""Capture the approved D9 repaired-reference fixture and mixed-background controls.

Exactly 37 complete dumps and 22 direct SGR observations: 96 terminal passes.
No candidate program is run and no candidate output constructs any expected cell.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
from d9_fixture import definitions, complex_bound, verify_background_delta


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    selected = definitions()
    print('BUNDLE complete-dumps=37 pen-status-observations=22 terminal-passes=96 hard-cap=40', flush=True)
    if args.list:
        for name, entry in selected.items():
            print(name, entry['kind'], 'original=%d repaired=%d' % (len(entry['original']), len(entry['input'])))
        return 0
    if not args.out:
        parser.error('--out required unless --list')
    args.out.mkdir(parents=True, exist_ok=False)
    runpy.run_path(str(ROOT / 'tools/vt/check_inverse.py'))['check']()
    baseline = json.loads((ROOT / 'tests/vt/reference/index.json').read_text())
    pen_pass = runpy.run_path(str(ROOT / 'tests/vt/probes/default_restoration.py'))['pen_pass']
    manifest = {'schema': 1, 'complete_dump_count': 37, 'pen_status_count': 22,
        'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
        'tracer_sha256': hashlib.sha256((ROOT / 'tools/vt/repair_background_fixture.py').read_bytes()).hexdigest(),
        'cases': {}, 'errors': [], 'mixed_background_disagreements': []}
    with oracle.Display() as display:
        for name, definition in selected.items():
            source = args.out / (name + '.in')
            source.write_bytes(definition['input'])
            (args.out / (name + '.original.in')).write_bytes(definition['original'])
            entry = {'kind': definition['kind'], 'size': definition['size'],
                'original_sha256': hashlib.sha256(definition['original']).hexdigest(),
                'input_sha256': hashlib.sha256(definition['input']).hexdigest(),
                'injections': definition['injections']}
            if 'original_case' in definition:
                entry['original_case'] = definition['original_case']
            try:
                cols, rows = definition['size']
                work = args.out / name
                got = oracle.dump(display, source.resolve(), cols, rows, work.resolve())
                raw = screen.dumps(got).encode()
                (work / 'got.screen').write_bytes(raw)
                entry['screen_sha256'] = hashlib.sha256(raw).hexdigest()
                if definition['kind'] == 'complex-repaired':
                    binding = baseline['suites']['fuzz-baseline'][name]
                    assert entry['original_sha256'] == binding['input_sha256']
                    original_path = ROOT / 'tests/vt/reference/fuzz-baseline' / (name + '.screen')
                    original_raw = original_path.read_bytes()
                    assert hashlib.sha256(original_raw).hexdigest() == binding['screen_sha256']
                    original = screen.loads(original_raw.decode())
                    cells, value = complex_bound(name, original)
                    verify_background_delta(original, got, cells, value)
                    entry.update(original_screen_sha256=binding['screen_sha256'],
                                 bound_cells=[list(cell) for cell in sorted(cells)],
                                 bound_field='background', corrected_background=value)
                elif definition['kind'] == 'minimal-repaired':
                    canonical = screen.loads(screen.dumps(got))
                    canonical['modes']['synchronized-output'] = 0  # D7, absent from these inputs.
                    assert not screen.compare(definition['written'], canonical), name
                    original_path = ROOT / 'tests/vt/reference/inverse' / definition['original_case'] / 'got.screen'
                    original = screen.loads(original_path.read_text())
                    cells = {(1, 1)} if definition['original_case'] not in (
                        'unsaved-explicit-default-then-inverse', 'restored-explicit-default-then-inverse',
                        'inactive-default-reset-then-bold', 'inactive-default-reset-then-underline') else set()
                    value = next((part for part in definition['written']['rows'][0][0][2].split(',') if part.startswith('bg=')), None)
                    verify_background_delta(original, got, cells, value)
                    entry.update(bound_cells=[list(cell) for cell in sorted(cells)], bound_field='background', corrected_background=value)
                else:
                    canonical = screen.loads(screen.dumps(got))
                    canonical['modes']['synchronized-output'] = 0
                    differences = screen.compare(definition['written'], canonical)
                    entry['written_differences'] = differences
                    if definition['kind'] == 'mixed-background-measurement' and differences:
                        manifest['mixed_background_disagreements'].append(name)
                if definition['pen_status']:
                    entry['sgr_report_hex'] = pen_pass(display, source, cols, rows, work / 'pen.json')
                entry['classification'] = 'measured-not-an-implicit-agreement'
                print('MEASURE %s kind=%s bounded-background-cells=%d' %
                      (name, definition['kind'], len(entry.get('bound_cells', []))), flush=True)
            except (AssertionError, oracle.OracleError, ValueError, OSError, subprocess.TimeoutExpired) as error:
                entry.update(classification='reference-fixture-error', error=str(error))
                manifest['errors'].append(name)
                print('MEASURE-ERROR %s %s' % (name, error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=37 errors=%d mixed-background-disagreements=%d' %
          (len(manifest['errors']), len(manifest['mixed_background_disagreements'])), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
