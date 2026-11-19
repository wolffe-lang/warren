#!/usr/bin/env python3
"""Canonical take manifests bind scripts and require the actual failing plant."""
from pathlib import Path
import hashlib
import re

ROOT = Path(__file__).resolve().parents[2]
RIG = ROOT / 'tests/vt/rig'
SESSION_RIG = ROOT / 'tests/session/rig'
CLIENT_RIG = ROOT / 'tests/client/rig'
PANE_RIG = ROOT / 'tests/pane/rig'


def main():
    for rig, filename, expected in (
        (RIG, 'w1-linux.manifest', ['w1-linux-gate', 'w1-resource', 'w1-widths', 'w1-recordings-lupin']),
        (RIG, 'w1-plant.manifest', ['w1-plant-build', 'vt-scalar-value']),
        (SESSION_RIG, 'w2-plant.manifest', ['w2-plant-build', 'one-image']),
        (CLIENT_RIG, 'w2-client-plant.manifest', ['w2-client-plant-build', 'console-policy']),
        (CLIENT_RIG, 'w2-lifecycle-plant.manifest', ['w2-lifecycle-plant-build', 'second-client']),
        (PANE_RIG, 'w3-plant.manifest', ['w3-plant-build', 'keys-reach-focused']),
        (PANE_RIG, 'w3-modes-plant.manifest', ['w3-modes-plant-build', 'hint-line']),
        (PANE_RIG, 'w3-bar-plant.manifest', ['w3-bar-plant-build', 'activity-marks']),
        (PANE_RIG, 'help-minute-plant.manifest', ['help-minute-plant-build', 'help-overlay-minute']),
        (CLIENT_RIG, 'w6-window-plant.manifest', ['w6-window-plant-build', 'zero-window']),
        (RIG, 'oracle-harness.manifest', ['oracle-harness-unit', 'oracle-harness-reference']),
        (RIG, 'oracle-retry-plant.manifest', ['signal-retry']),
        (RIG, 'oracle-bound-plant.manifest', ['retry-bound']),
        (RIG, 'oracle-nightly-plant.manifest', ['nightly-limit']),
        (RIG, 'oracle-known-plant.manifest', ['known-fixed']),
        (RIG, 'oracle-jump-plant.manifest', ['jump-scroll-off'])):
        raw = (rig / filename).read_text()
        steps = re.findall(r'^step (\S+)', raw, re.M)
        assert steps == expected
        scripts = re.findall(r'^rig (\S+) sha256=([a-f0-9]{64})$', raw, re.M)
        assert scripts
        for relative, digest in scripts:
            assert hashlib.sha256((rig / relative).read_bytes()).hexdigest() == digest
        assert 'floor ' in raw
    plant = (RIG / 'w1-plant-step.sh').read_text()
    assert 'FAIL vt-scalar-value ' in plant and 'exit "$rc"' in plant
    assert '[ "$rc" -eq 134 ]' in plant
    server_plant = (SESSION_RIG / 'w2-plant-step.sh').read_text()
    assert 'never-ack-beside-active resize-crossing-image' in server_plant
    client_plant = (CLIENT_RIG / 'w2-client-plant-step.sh').read_text()
    assert 'FAIL console-policy ' in client_plant and 'client_render_test.lu' in client_plant
    lifecycle_plant = (CLIENT_RIG / 'w2-lifecycle-plant-step.sh').read_text()
    assert 'client-rows" "$root/target/native/warren" second-client' in lifecycle_plant
    pane_plant = (PANE_RIG / 'w3-plant-step.sh').read_text()
    assert 'pane-rows" "$root/target/native/warren" keys-reach-focused split-sizes' in pane_plant
    modes_plant = (PANE_RIG / 'w3-modes-plant-step.sh').read_text()
    assert 'pane-rows" "$root/target/native/warren" hint-line confirm-close' in modes_plant
    bar_plant = (PANE_RIG / 'w3-bar-plant-step.sh').read_text()
    assert 'pane-rows" "$root/target/native/warren" activity-marks zoom-mark' in bar_plant
    minute_plant = (PANE_RIG / 'help-minute-plant-step.sh').read_text()
    assert 'pane-rows" "$root/target/native/warren" help-overlay-minute help-overlay' in minute_plant
    window_plant = (CLIENT_RIG / 'w6-window-plant-step.sh').read_text()
    assert 'client-rows" "$root/target/native/warren" zero-window window-too-large' in window_plant
    harness = (RIG / 'oracle-harness-step.sh').read_text()
    assert "printf 'FAIL signal-retry " in harness and 'display_retry_rows.py' in harness
    assert "printf 'FAIL retry-bound " in harness and 'rate-bound-ordinary-runner' in harness
    assert "printf 'FAIL nightly-limit " in harness and 'test_nightly_fits_its_limit' in harness
    assert "printf 'FAIL known-fixed " in harness and 'fresh-known known-passes' in harness
    assert "printf 'FAIL jump-scroll-off " in harness and 'jump_scroll_rows.py' in harness
    assert '--case fresh-0901 --case fresh-2265 --case fresh-2536' in harness
    assert 'tests/vt/fresh_fuzz.py --profile pull-request' in harness and 'exec bash tools/gate unit' in harness
    linux = (RIG / 'w1-step.sh').read_text()
    assert 'tools/gate linux' in linux and 'vt_resource_bench.lu' in linux
    assert 'width_sweep.py' in linux and '--suite recordings' in linux
    print('PASS canonical-rigs exact-planned-steps script-hashes actual-plant-failure no-record-replay')


if __name__ == '__main__':
    main()
