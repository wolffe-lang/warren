#!/usr/bin/env python3
"""66 raw A/S frames plus two status processes: at most134 xterms.

Three zero-width scalars cross22 valid cursor/left-cell contexts. Before/after
CPR and DECCIR are measured, not inferred from a candidate. Failed ordinary
frame validation is retained alongside full-cell print observations.
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
import run as oracle
import screen
from feeder import Tty
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'


def cases():
    wide = '中'.encode()
    prefixes = {
        'cup-unwritten-left': C + b'5G',
        'cup-written-left': b'abcd' + C + b'5G',
        'print-written-left': b'abcd',
        'print-written-blank-left': b'abc ',
        'cup-written-blank-left': b'abc ' + C + b'5G',
        'cup-erased-left': C + b'4G' + C + b'X' + C + b'5G',
        'cup-gap-left': C + b'8GZ' + C + b'5G',
        'cup-painted-left': C + b'45m' + C + b'4G' + C + b'K' + C + b'5G',
        'print-wide-tail-left': b'ab' + wide,
        'cup-wide-tail-left': b'ab' + wide + C + b'5G',
        'cup-first-empty': C + b'1G',
        'cr-first-empty': C + b'5G\r',
        'cr-first-written': b'abcd\r',
        'cup-first-written': b'abcd' + C + b'1G',
        'pending-unwritten-left': C + b'12GZ',
        'pending-written-left': b'abcdefghijkl',
        'pending-wide-tail-under': C + b'11G' + wide,
        'clear-last-unwritten-left': C + b'12GZ' + C + b'12G',
        'clear-last-written-left': b'abcdefghijkl' + C + b'12G',
        'clear-last-wide-tail-under': C + b'11G' + wide + C + b'12G',
    }
    result = {}
    for cp in (0x301, 0x1161, 0x13430):
        for name, body in prefixes.items():
            result['place-%04X-%s' % (cp, name)] = (HEAD + body, cp, name, 12, 4)
        for name, body in (('pending-first-column', b'X'), ('clear-first-column', b'X' + C + b'1G')):
            result['place-%04X-%s' % (cp, name)] = (HEAD + body, cp, name, 1, 4)
    assert len(result) == 66
    return result


def status_inner(out, cols):
    old = termios.tcgetattr(0)
    records = {}
    try:
        tty.setraw(0)
        terminal = Tty(20)
        for name, (prefix, cp, context, width, rows) in cases().items():
            if width != cols:
                continue
            terminal.write(E + b'c' + prefix)
            terminal.sync()
            before = {'cpr_hex': terminal.ask(C + b'6n', b'R').hex(),
                      'deccir_hex': terminal.ask(C + b'1$w', E + b'\\').hex()}
            terminal.write(chr(cp).encode())
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


def status_pass(display, out, cols):
    command = ['xterm', '-u8', '-geometry', '%dx4' % cols, '-fn', 'fixed']
    for key, value in oracle.RESOURCES.items():
        command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
    command += ['-e', sys.executable, '-I', str(Path(__file__).resolve()), '--status-inner',
                '--cols', str(cols), '--out', str(out.resolve())]
    env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
           'HOME': str(out.parent.resolve()), 'TERM': 'xterm-256color'}
    done = subprocess.run(command, env=env, capture_output=True, timeout=180)
    assert done.returncode == 0 and out.exists(), (done.returncode, done.stderr[-500:])
    result = json.loads(out.read_text())
    assert 'error' not in result, result
    return result


def full_cell_observations(s, tails, cols, rows, cp):
    """Read the copied cells for diagnostics; never repair A's extent report."""
    observed = []
    for r, line in enumerate(oracle.parse_print(s['print'], rows)):
        at = cols - len(tails[r])
        for c in range(cols):
            if c + 1 in tails[r]:
                continue
            assert line[at][0] == [32] and line[at][1] == oracle.SEPARATOR_BG[(c + 1) % 2]
            chars = line[at + 1][0]
            if cp in chars:
                observed.append([r + 1, c + 1, chars])
            at += 2
            if c + 2 in tails[r]:
                assert line[at][0] == [32]
                at += 1
        assert at == len(line)
    return observed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--status-inner', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--cols', type=int)
    args = parser.parse_args()
    if args.status_inner:
        return status_inner(args.out, args.cols)
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'frame_count': 66, 'terminal_process_budget': 134, 'cases': {}, 'errors': []}
    print('BUNDLE raw-frames=66 status-processes=2 terminal-processes-at-most=134 CPR-queries=132 DECCIR-queries=132', flush=True)
    with oracle.Display() as display:
        statuses = {}
        for cols in (12, 1):
            statuses.update(status_pass(display, args.out / ('status-%d.json' % cols), cols))
        for name, (prefix, cp, context, cols, rows) in cases().items():
            data = prefix + chr(cp).encode()
            path = args.out / (name + '.in')
            path.write_bytes(data)
            work = args.out / name
            work.mkdir()
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'scalar': 'U+%04X' % cp,
                     'context': context, 'size': [cols, rows], 'status': statuses[name]}
            try:
                a = oracle.run_pass(display, 'A', path.resolve(), cols, rows, work.resolve())
                tails = [[c + 1 for c, checksum in enumerate(row) if checksum == '0000'] for row in a['checksums']]
                layout = work / 'continuation.json'
                layout.write_text(json.dumps(tails))
                s = oracle.run_pass(display, 'S', path.resolve(), cols, rows, work.resolve(), extra=[layout])
                entry['observed_mark_cells'] = full_cell_observations(s, tails, cols, rows, cp)
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
    print('MEASUREMENTS cases=66 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
