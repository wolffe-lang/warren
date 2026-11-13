#!/usr/bin/env python3
"""Measure every assigned Unicode scalar through batched reference CPRs.

Measurements are not implicit agreement. All disagreements are enumerated;
Cc controls are measured but never misreported as scalar-width disagreements.
The reference binary is only run, never read as implementation source.
"""
import argparse
from collections import Counter
import hashlib
from itertools import islice
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import time
import termios
import traceback
import tty

ROOT = Path(__file__).resolve().parents[2]
CPR = re.compile(rb'\x1b\[([1-9][0-9]*);([1-9][0-9]*)R')
BATCH = 128


def commands(points):
    # The ASCII base makes combining widths observable. CAN/ST also return
    # C1 string introducers to ground before CPR; neither moves the cursor.
    return b''.join(b'\x1b[1;1H\x1b[2Ka' + chr(cp).encode('utf-8') + b'\x18\x1b\\\x1b[6n'
                    for cp in points)


def positions(data, count):
    matches = list(CPR.finditer(data))
    if len(matches) != count or CPR.sub(b'', data):
        raise ValueError('width CPR count/framing mismatch: %r' % data[:160])
    return [(int(match[1]), int(match[2])) for match in matches]


def inner(out, native_path):
    sys.path.insert(0, str(ROOT / 'tools/oracle'))
    from feeder import Tty
    assigned_path = ROOT / 'tests/vt/assigned-ranges.json'
    widths_path = ROOT / 'tests/vt/width-ranges.json'
    assigned = json.loads(assigned_path.read_text())
    widths = json.loads(widths_path.read_text())
    if assigned['version'] != widths['version']:
        raise ValueError('assigned and width Unicode versions differ')
    if native_path.stat().st_size != 0x110000:
        raise ValueError('native width vector is missing code points')
    native = native_path.read_bytes()
    expected_vector = runpy.run_path(str(ROOT / 'tests/vt/width_vector_rows.py'))['expected_vector']
    if native != expected_vector():
        raise ValueError('native width vector differs from the pinned table')

    def expected(cp):
        return native[cp]

    points = ((cp, category) for low, high, category in assigned['ranges'] for cp in range(low, high + 1))
    terminal = Tty(20)
    old = termios.tcgetattr(0)
    measured = 0
    disagreements = []
    classes = Counter()
    controls = []
    try:
        tty.setraw(0)
        terminal.write(b'\x1b(B\x1b)B\x0f\x1b[?6l\x1b[r\x1b[0m')
        with (out / 'measurements.tsv').open('w') as table, (out / 'replies.bin').open('wb') as raw, \
                (out / 'progress.jsonl').open('w') as progress:
            table.write('scalar\tcategory\texpected-width\trow\tcol\tclassification\n')
            while True:
                batch = list(islice(points, BATCH))
                if not batch:
                    break
                terminal.write(commands([cp for cp, _ in batch]))
                replies = terminal.read_until(lambda data: len(CPR.findall(data)) >= len(batch) and data.endswith(b'R'))
                raw.write(replies)
                for (cp, category), (row, col) in zip(batch, positions(replies, len(batch))):
                    want = expected(cp)
                    got = col - 2 if row == 1 else None
                    classification = 'control' if category == 'Cc' else 'equal' if got == want else \
                        'reference-non-width-position' if got not in (0, 1, 2) else \
                        'native-%d-reference-%d' % (want, got)
                    entry = {'scalar': 'U+%04X' % cp, 'category': category, 'expected': want,
                             'row': row, 'col': col, 'classification': classification}
                    if category == 'Cc':
                        controls.append(entry)
                    elif got != want:
                        disagreements.append(entry)
                    classes[classification] += 1
                    table.write('%s\t%s\t%d\t%d\t%d\t%s\n' %
                                (entry['scalar'], category, want, row, col, classification))
                    measured += 1
                if measured % 4096 == 0 or measured == assigned['assigned_scalars']:
                    progress.write(json.dumps({'measured': measured, 'total': assigned['assigned_scalars']}) + '\n')
                    progress.flush()
        if measured != assigned['assigned_scalars']:
            raise ValueError('assigned scalar count differs from the generated census')
        result = {'schema': 1, 'status': 'measured-not-an-agreement-verdict', 'unicode': assigned['version'],
                  'assigned_sha256': hashlib.sha256(assigned_path.read_bytes()).hexdigest(),
                  'widths_sha256': hashlib.sha256(widths_path.read_bytes()).hexdigest(),
                  'native_vector_sha256': hashlib.sha256(native).hexdigest(),
                  'measured_scalars': measured, 'excluded_non_scalars': assigned['excluded_non_scalars'],
                  'batch_size': BATCH, 'classifications': dict(sorted(classes.items())),
                  'controls': controls, 'disagreements': disagreements}
        for name in ('measurements.tsv', 'replies.bin'):
            result[name + '_sha256'] = hashlib.sha256((out / name).read_bytes()).hexdigest()
        (out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-vector', type=Path, required=True,
                        help='validated output of the actual native vt_width_vector program')
    parser.add_argument('--inner', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    out = args.out.resolve()
    if args.inner:
        try:
            inner(out, args.native_vector.resolve())
            return 0
        except Exception as error:
            (out / 'error.json').write_text(json.dumps({'error': str(error), 'traceback': traceback.format_exc()}) + '\n')
            return 1
    out.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(ROOT / 'tools/oracle'))
    import run as oracle
    with oracle.Display() as display, (out / 'terminal.log').open('wb') as log:
        command = ['xterm', '-u8', '-geometry', '12x4', '-fn', 'fixed']
        for key, value in oracle.RESOURCES.items():
            command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
        command += ['-e', sys.executable, '-I', str(Path(__file__).resolve()), '--inner', '--out', str(out),
                    '--native-vector', str(args.native_vector.resolve())]
        env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
               'HOME': str(out), 'TERM': 'xterm-256color'}
        proc = subprocess.Popen(command, env=env, stdout=log, stderr=log)
        deadline = time.monotonic() + 1800
        try:
            while True:
                if time.monotonic() >= deadline:
                    raise TimeoutError('full assigned-scalar sweep exceeded 1800 seconds')
                try:
                    code = proc.wait(timeout=30)
                    break
                except subprocess.TimeoutExpired:
                    progress = out / 'progress.jsonl'
                    lines = progress.read_text().splitlines() if progress.exists() else []
                    print('MEASURE width-progress ' + (lines[-1] if lines else 'waiting for first batch'), flush=True)
        except BaseException:
            proc.terminate()
            proc.wait()
            raise
    result_path = out / 'result.json'
    if code or not result_path.exists() or (out / 'error.json').exists():
        print('FAIL width-measurement emulator-exit=%d result=%s' % (code, result_path.exists()))
        return 1
    result = json.loads(result_path.read_text())
    print('MEASURE widths assigned=%d controls=%d disagreements=%d (not an agreement verdict)' %
          (result['measured_scalars'], len(result['controls']), len(result['disagreements'])), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
