#!/usr/bin/env python3
"""Reject ambiguous palette forms instead of ignoring a reported foreground."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
from expectations import blank, text_row
from checkpoint_expectations import foreground_palette, written_checkpoint


def recording(data):
    return b'warren-rec 1\nsize 12 4\no %d\n' % len(data) + data + b'\n'


def main():
    data = recording(b'\x1b[30m\x1b[93m\x1b[1;94m\x1b[96m')
    assert foreground_palette(data) == {0, 11, 12, 14}
    reference = blank(12, 4)
    text_row(reference, 0, [88], 'bold,fg=idx:4')
    labels, written = written_checkpoint('recording-quarry-resize-1', data, reference)
    assert labels == ['RPT-BRIGHT-BOLD-COLOUR']
    assert written['rows'][0][0][2] == 'bold,fg=idx:12'
    assert reference['rows'][0][0][2] == 'bold,fg=idx:4'
    ambiguous = recording(b'\x1b[30m\x1b[93m\x1b[94m\x1b[96m\x1b[34m')
    try:
        written_checkpoint('recording-quarry-resize-1', ambiguous, reference)
    except AssertionError:
        pass
    else:
        raise AssertionError('ambiguous low+bright input accepted as an unambiguous written form')
    print('PASS report-form source-palette-bound exact-bright-value no-mutation ambiguous-refusal')


if __name__ == '__main__':
    main()
