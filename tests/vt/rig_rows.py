#!/usr/bin/env python3
"""Canonical take manifests bind scripts and require the actual failing plant."""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[2]
RIG = ROOT / 'tests/vt/rig'


def main():
    for filename, expected in (
        ('w1-linux.manifest', ['w1-linux-gate', 'w1-resource', 'w1-widths', 'w1-recordings-lupin']),
        ('w1-plant.manifest', ['w1-plant-build', 'vt-scalar-value'])):
        raw = (RIG / filename).read_text()
        steps = re.findall(r'^step (\S+)', raw, re.M)
        assert steps == expected
        scripts = re.findall(r'^rig (\S+) sha256=([a-f0-9]{64})$', raw, re.M)
        assert scripts
        for relative, digest in scripts:
            assert hashlib.sha256((RIG / relative).read_bytes()).hexdigest() == digest
        assert 'floor ' in raw
    plant = (RIG / 'w1-plant-step.sh').read_text()
    assert 'FAIL vt-scalar-value ' in plant and 'exit "$rc"' in plant
    assert '[ "$rc" -eq 134 ]' in plant
    linux = (RIG / 'w1-step.sh').read_text()
    assert 'tools/gate linux' in linux and 'vt_resource_bench.lu' in linux
    assert 'width_sweep.py' in linux and '--suite recordings' in linux
    print('PASS canonical-rigs exact-planned-steps script-hashes actual-plant-failure no-record-replay')


if __name__ == '__main__':
    main()
