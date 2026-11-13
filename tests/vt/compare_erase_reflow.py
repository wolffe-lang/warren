#!/usr/bin/env python3
"""Targeted full-frame D6 coverage of erased paint through resize-only paths."""
import argparse
import copy
from pathlib import Path
import runpy
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import screen
from erase_reflow_expected import expected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command
    cases = runpy.run_path(str(ROOT / 'tests/vt/probes/fresh_erase_reflow.py'))['cases']()
    out = ROOT / 'target/vt/erase-reflow-contract'
    out.mkdir(parents=True, exist_ok=True)
    failed = 0
    for name, (data, kind, background, phase) in cases.items():
        contract = expected(kind, background == 'painted', phase)
        done = subprocess.run(args.command + ['vt-dump', '--history-bytes', '4096', '--replay'],
                              input=data, capture_output=True, cwd=ROOT, timeout=180)
        (out / (name + '.stdout')).write_bytes(done.stdout)
        (out / (name + '.stderr')).write_bytes(done.stderr)
        differences = [('exit', str(done.returncode))] if done.returncode or done.stderr else screen.compare(contract, screen.loads(done.stdout.decode()))
        if differences:
            print('FAIL erase-reflow-contract', name, differences[:12], flush=True)
            failed += 1
        else:
            print('PASS erase-reflow-contract', name, 'D6 independent-complete-frame', flush=True)
    # A missing painted suffix must actually turn this new gate red.
    base = expected('after-last-glyph', True, 'narrowed')
    planted = copy.deepcopy(base)
    planted['rows'][1][0][2] = '-'
    assert ('cell-attribute', 'r2c1 bg=idx:5: expected bg=idx:5 got -') in screen.compare(base, planted)
    planted = copy.deepcopy(base)
    planted['extents'][1] = 0
    assert any(name == 'row-extent' for name, _ in screen.compare(base, planted))
    print('ERASE-REFLOW-CONTRACT frames=24 failed=%d painted-suffix-and-extent-plants-rejected' % failed, flush=True)
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
