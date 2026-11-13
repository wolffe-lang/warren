#!/usr/bin/env python3
"""Finite named-red diagnostics: default-colour restore and sparse cell repair.

Twenty complete A/S dumps plus twenty direct SGR status observations, sixty
terminal processes total. The reference is only run as a pinned binary.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import subprocess
import sys
import termios
import tty

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen
from feeder import Tty, load, replay
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'
H, L = C + b'?1049h', C + b'?1049l'
BG = C + b'48;5;181m'
RGB = b'2;237;31;126m'


def cases():
    bodies = {
        'default-bg-save-rgb-restore': E + b'7' + C + b'48;' + RGB + E + b'8X',
        'default-fg-save-rgb-restore': E + b'7' + C + b'38;' + RGB + E + b'8X',
        'default-bg-with-fg-save': C + b'97m' + E + b'7' + BG + E + b'8X',
        'default-fg-with-bg-save': C + b'44m' + E + b'7' + C + b'38;' + RGB + E + b'8X',
        'valid-default-inactive-reset-after-bg': H + L + BG + L + b'X',
        'valid-default-inactive-reset-after-bg-clear': H + L + BG + L + H,
        'repeat-bg-restore-after-fg': H + BG + H + L + C + b'36;9m' + L + H,
        'fg-saved-repeat-bg-restore-after-fg': C + b'97m' + H + BG + H + L + C + b'36;9m' + L + H,
        'fg-saved-repeat-bg-double-reset': C + b'97m' + H + BG + H + L + L + H,
        'fg-saved-repeat-bg-restore-pen': C + b'97m' + H + BG + H + L + C + b'36;9m' + L + b'X',
        'sparse-ich-last-written-discarded': b'ab' + C + b'12GZ' + C + b'3G' + C + b'@',
        'partial-ech-wide-lead': '中'.encode() + C + b'1G' + C + b'X',
        'partial-el-left-wide-lead': '中'.encode() + C + b'1G' + C + b'1K',
        'wide-overwrite-gap-then-ich': '中'.encode() + C + b'1Gx' + C + b'2G' + C + b'@',
    }
    result = {name: (HEAD + body, 12, 4) for name, body in bodies.items()}
    fuzz = runpy.run_path(str(ROOT / 'tools/corpus/fuzz.py'))['stream']
    for seed in (10, 16, 19):
        result['full-seed-%02d' % seed] = (HEAD + fuzz(seed, 2048), 80, 24)
    source = fuzz(16, 2048)
    switches = list(re.finditer(rb'\x1b\[\?1049[hl]', source))
    for name, at in (('seed16-before-last-reset', switches[-2].start()),
                     ('seed16-after-last-reset', switches[-2].end()),
                     ('seed16-before-final-enter', switches[-1].start())):
        result[name] = (HEAD + source[:at], 80, 24)
    assert len(result) == 20
    return result


def pen_inner(source, out):
    old = termios.tcgetattr(0)
    try:
        tty.setraw(0)
        terminal = Tty(20)
        replay(terminal, load(source))
        answer = terminal.ask(b'\x1bP$qm\x1b\\', b'\x1b\\')
        if not (answer.startswith(b'\x1bP1$r') and answer.endswith(b'm\x1b\\')):
            raise ValueError('reference did not return a valid SGR status string: %r' % answer)
        out.write_text(json.dumps({'sgr_report_hex': answer.hex()}) + '\n')
    except Exception as error:
        out.write_text(json.dumps({'error': str(error)}) + '\n')
        return 1
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)
    return 0


def pen_pass(display, source, cols, rows, out):
    command = ['xterm', '-u8', '-geometry', '%dx%d' % (cols, rows), '-fn', 'fixed']
    for key, value in oracle.RESOURCES.items():
        command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
    command += ['-e', sys.executable, '-I', str(Path(__file__).resolve()), '--pen-inner',
                str(source.resolve()), '--pen-out', str(out.resolve())]
    env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
           'HOME': str(out.parent.resolve()), 'TERM': 'xterm-256color'}
    done = subprocess.run(command, env=env, capture_output=True, timeout=60)
    if done.returncode or not out.exists():
        raise ValueError('pen-status terminal failed exit=%d' % done.returncode)
    record = json.loads(out.read_text())
    if 'error' in record:
        raise ValueError(record['error'])
    return record['sgr_report_hex']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--list', action='store_true')
    parser.add_argument('--pen-inner', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--pen-out', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.pen_inner:
        return pen_inner(args.pen_inner, args.pen_out)
    selected = cases()
    print('BUNDLE complete-dumps=20 pen-status-observations=20 terminal-passes=60 hard-cap=24', flush=True)
    if args.list:
        for name in selected:
            print(name)
        return 0
    if not args.out:
        parser.error('--out required unless --list')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'complete_dump_count': 20, 'pen_status_count': 20,
                'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
                'cases': {}, 'errors': []}
    with oracle.Display() as display:
        for name, (data, cols, rows) in selected.items():
            source = args.out / (name + '.in')
            source.write_bytes(data)
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'size': [cols, rows]}
            try:
                work = args.out / name
                got = oracle.dump(display, source.resolve(), cols, rows, work.resolve())
                encoded = screen.dumps(got).encode()
                (work / 'got.screen').write_bytes(encoded)
                sgr = pen_pass(display, source, cols, rows, work / 'pen.json')
                entry.update(screen_sha256=hashlib.sha256(encoded).hexdigest(), sgr_report_hex=sgr, classification='measured')
                print('MEASURE %s SGR=%s' % (name, sgr), flush=True)
            except (oracle.OracleError, ValueError, OSError, subprocess.TimeoutExpired) as error:
                entry.update(classification='reference-measurement-error', error=str(error))
                manifest['errors'].append(name)
                print('MEASURE-ERROR %s %s' % (name, error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=20 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
