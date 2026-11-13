#!/usr/bin/env python3
"""34 raw frames plus one status process: at most69 terminal processes.

The preceding66-frame matrix established identical placement for acute, jamo
and Egyptian controls; this matrix isolates anchor-clearing operations with
acute and measures both cursor reports around it.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import termios
import tty

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt/probes'))
import run as oracle
import screen
from feeder import Tty, replay
from combining_placement import full_cell_observations
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'
MARK = '́'.encode()


def cases():
    bodies = {'baseline': b'', 'cup-same': C + b'1;5H', 'cr': b'\r', 'lf': b'\n',
              'bs': b'\b', 'ht': b'\t', 'sgr': C + b'31m',
              'ech-not-anchor': C + b'X', 'el-not-anchor': C + b'K',
              'el-through-anchor': C + b'1K', 'save': E + b'7',
              'save-restore-same': E + b'7' + E + b'8',
              'alt47-enter': C + b'?47h', 'alt47-roundtrip': C + b'?47h' + C + b'?47l',
              'alt1049-enter': C + b'?1049h', 'alt1049-roundtrip': C + b'?1049h' + C + b'?1049l',
              'alt1049-print-return': C + b'?1049hX' + C + b'?1049l',
              'second-mark': MARK, 'cup-then-second-mark': C + b'1;5H' + MARK}
    for final in 'CDAB':
        for value in (0, 1):
            bodies['motion-%s-%d' % (final, value)] = C + str(value).encode() + final.encode()
    result = {name: ([('o', HEAD + b'abcd' + body)], 12, 4) for name, body in bodies.items()}
    result['restore-earlier'] = ([('o', HEAD + E + b'7abcd' + E + b'8')], 12, 4)
    for name, size in (('resize-same', (12, 4)), ('resize-narrow', (6, 8))):
        result[name] = ([('o', HEAD + b'abcd'), ('r', *size)], 12, 4)
    for name, body in (('pending-baseline', b''), ('pending-ech-through-anchor', C + b'X'),
                       ('pending-el-through-anchor', C + b'K'), ('pending-sgr', C + b'31m')):
        result[name] = ([('o', HEAD + b'abcd' + body)], 4, 4)
    assert len(result) == 34, len(result)
    return result


def encode(events, cols, rows):
    result = bytearray(b'warren-rec 1\nsize %d %d\n' % (cols, rows))
    for event in events + [('o', MARK)]:
        if event[0] == 'o':
            result.extend(b'o %d\n' % len(event[1]) + event[1] + b'\n')
        else:
            result.extend(b'r %d %d\n' % event[1:])
    return bytes(result)


def status_inner(out):
    old = termios.tcgetattr(0)
    records = {}
    try:
        tty.setraw(0)
        terminal = Tty(20)
        for name, (events, cols, rows) in cases().items():
            replay(terminal, [('r', cols, rows), ('o', E + b'c')] + events)
            terminal.sync()
            before = {'cpr_hex': terminal.ask(C + b'6n', b'R').hex(),
                      'deccir_hex': terminal.ask(C + b'1$w', E + b'\\').hex()}
            terminal.write(MARK)
            terminal.sync()
            after = {'cpr_hex': terminal.ask(C + b'6n', b'R').hex(),
                     'deccir_hex': terminal.ask(C + b'1$w', E + b'\\').hex()}
            records[name] = {'before': before, 'after': after}
        out.write_text(json.dumps(records, indent=2) + '\n')
        return 0
    except Exception as error:
        out.write_text(json.dumps({'error': str(error)}) + '\n')
        return 1
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--status-inner', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.status_inner:
        return status_inner(args.out)
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'frame_count': 34, 'terminal_process_budget': 69, 'cases': {}, 'errors': []}
    print('BUNDLE raw-frames=34 status-processes=1 terminal-processes-at-most=69 CPR-queries=68 DECCIR-queries=68', flush=True)
    with oracle.Display() as display:
        status = args.out / 'status.json'
        command = ['xterm', '-u8', '-geometry', '12x4', '-fn', 'fixed']
        for key, value in oracle.RESOURCES.items():
            command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
        command += ['-e', sys.executable, '-I', str(Path(__file__).resolve()), '--status-inner', '--out', str(status.resolve())]
        env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
               'HOME': str(args.out.resolve()), 'TERM': 'xterm-256color'}
        done = subprocess.run(command, env=env, capture_output=True, timeout=180)
        assert done.returncode == 0 and status.exists(), (done.returncode, done.stderr[-500:])
        statuses = json.loads(status.read_text())
        assert 'error' not in statuses, statuses
        for name, (events, cols, rows) in cases().items():
            data = encode(events, cols, rows)
            path = args.out / (name + '.rec')
            path.write_bytes(data)
            work = args.out / name
            work.mkdir()
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'initial_size': [cols, rows],
                     'status': statuses[name]}
            try:
                a = oracle.run_pass(display, 'A', path.resolve(), cols, rows, work.resolve())
                final_cols, final_rows = a['size']
                tails = [[c + 1 for c, checksum in enumerate(row) if checksum == '0000'] for row in a['checksums']]
                layout = work / 'continuation.json'
                layout.write_text(json.dumps(tails))
                s = oracle.run_pass(display, 'S', path.resolve(), cols, rows, work.resolve(), extra=[layout])
                entry['observed_mark_cells'] = full_cell_observations(s, tails, final_cols, final_rows, 0x301)
                assert a['cpr'].encode().hex() == statuses[name]['after']['cpr_hex']
                try:
                    frame = oracle.finish(oracle.describe(a), a, s)
                    (work / 'got.screen').write_text(screen.dumps(frame))
                    entry['classification'] = 'complete-reference-frame'
                except (oracle.OracleError, ValueError) as error:
                    entry.update(classification='strict-report-failure', validator_error=str(error))
                print('MEASURE %s marks=%s status=%s class=%s' %
                      (name, entry['observed_mark_cells'], statuses[name], entry['classification']), flush=True)
            except (AssertionError, oracle.OracleError, ValueError, OSError) as error:
                entry['error'] = str(error)
                manifest['errors'].append(name)
                print('MEASURE-ERROR', name, str(error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=34 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
