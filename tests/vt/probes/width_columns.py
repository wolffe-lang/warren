#!/usr/bin/env python3
"""Exactly 350 libc wcwidth calls, two wcswidth pairs and two reference CPRs.

The pinned std has no display-width API: that column is unavailable, not
char count or byte padding presented as terminal-cell width.
"""
import argparse
import ctypes
import hashlib
import json
import locale
import os
from pathlib import Path
import subprocess
import sys
import termios
import tty

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/vt'))
from check_width_policy import expected_differences
from width_sweep import positions
PAIRS = {'US': (0x1F1FA, 0x1F1F8), 'GB': (0x1F1EC, 0x1F1E7)}


def pair_inner(out):
    sys.path.insert(0, str(ROOT / 'tools/oracle'))
    from feeder import Tty
    old = termios.tcgetattr(0)
    try:
        tty.setraw(0)
        terminal = Tty(20)
        terminal.write(b'\x1b(B\x1b)B\x0f\x1b[?6l\x1b[r\x1b[0m')
        result = {}
        for name, points in PAIRS.items():
            body = ''.join(chr(cp) for cp in points).encode()
            terminal.write(b'\x1b[1;1H\x1b[2Ka' + body + b'\x18\x1b\\')
            reply = terminal.ask(b'\x1b[6n', b'R')
            row, col = positions(reply, 1)[0]
            result[name] = {'reply_hex': reply.hex(), 'row': row, 'col': col,
                            'advance': col - 2 if row == 1 else None}
        out.write_text(json.dumps(result, indent=2) + '\n')
        return 0
    except Exception as error:
        out.write_text(json.dumps({'error': str(error)}) + '\n')
        return 1
    finally:
        termios.tcsetattr(0, termios.TCSANOW, old)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--native-vector', type=Path)
    parser.add_argument('--warren')
    parser.add_argument('--warren-head')
    parser.add_argument('--inner', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.inner:
        return pair_inner(args.out.resolve())
    if not args.native_vector or not args.warren or not args.warren_head:
        parser.error('--native-vector, --warren and --warren-head required')
    args.out.mkdir(parents=True, exist_ok=False)
    locale_name = locale.setlocale(locale.LC_ALL, 'C.UTF-8')
    libc = ctypes.CDLL('libc.so.6')
    libc.wcwidth.argtypes = [ctypes.c_wchar]
    libc.wcwidth.restype = ctypes.c_int
    libc.wcswidth.argtypes = [ctypes.c_wchar_p, ctypes.c_size_t]
    libc.wcswidth.restype = ctypes.c_int
    libc.gnu_get_libc_version.restype = ctypes.c_char_p
    vector = args.native_vector.read_bytes()
    import runpy
    assert vector == runpy.run_path(str(ROOT / 'tests/vt/width_vector_rows.py'))['expected_vector']()
    entries = expected_differences()
    assert len(entries) == 350
    rows = []
    for entry in entries:
        cp = int(entry['scalar'][2:], 16)
        assert vector[cp] == entry['expected']
        rows.append({'scalar': entry['scalar'], 'warren': vector[cp],
                     'std': 'unavailable at this pin', 'libc_wcwidth': libc.wcwidth(chr(cp)),
                     'reference': entry['col'] - 2})
    sys.path.insert(0, str(ROOT / 'tools/oracle'))
    import run as oracle
    import screen
    pair_file = args.out.resolve() / 'reference-pairs.json'
    with oracle.Display() as display:
        command = ['xterm', '-u8', '-geometry', '12x4', '-fn', 'fixed']
        for key, value in oracle.RESOURCES.items():
            command += ['-xrm', 'XTerm*%s: %s' % (key, value)]
        command += ['-e', sys.executable, '-I', str(Path(__file__).resolve()), '--inner', '--out', str(pair_file)]
        env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
               'HOME': str(args.out.resolve()), 'TERM': 'xterm-256color'}
        done = subprocess.run(command, env=env, capture_output=True, timeout=60)
        assert done.returncode == 0 and pair_file.exists(), (done.returncode, done.stderr)
    reference = json.loads(pair_file.read_text())
    assert set(reference) == set(PAIRS)
    pairs = {}
    for name, points in PAIRS.items():
        value = ''.join(chr(cp) for cp in points)
        native = subprocess.run([args.warren, 'vt-dump', '--cols', '12', '--rows', '4', '--history-bytes', '0'],
                                input=b'a' + value.encode(), capture_output=True, timeout=30)
        assert native.returncode == 0 and not native.stderr
        (args.out / (name + '.native.screen')).write_bytes(native.stdout)
        frame = screen.loads(native.stdout.decode())
        pairs[name] = {'scalars': ['U+%04X' % cp for cp in points],
            'warren_actual_advance': frame['cursor']['col'] - 2 if frame['cursor']['row'] == 1 else None,
            'std': 'unavailable at this pin', 'libc_wcswidth': libc.wcswidth(value, 2),
            'reference': reference[name]}
    result = {'schema': 1, 'std_commit': '77cf3210a82c93dc05ded987c249bb69e79b0a89',
        'std_function': None, 'std_status': 'unavailable at this pin', 'locale': locale_name,
        'libc_version': libc.gnu_get_libc_version().decode(),
        'native_vector_sha256': hashlib.sha256(vector).hexdigest(),
        'native_warren_sha256': hashlib.sha256(Path(args.warren).read_bytes()).hexdigest(),
        'native_warren_head': args.warren_head,
        'oracle_pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
        'scalars': rows, 'pairs': pairs}
    (args.out / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
    print('MEASURE width-columns scalars=350 libc=wcwidth std=unavailable pairs=2 actual-native+libc-wcswidth+reference-CPR')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
