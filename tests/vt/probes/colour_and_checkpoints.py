#!/usr/bin/env python3
"""Finite saved-colour diagnostics, ASCII prefix witnesses and resize checkpoints."""
import argparse
import hashlib
from io import BytesIO
import json
from pathlib import Path
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen
sys.path.insert(0, str(ROOT / 'tests/vt'))
from reference_inputs import fixture_input

E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'


def cases():
    result = {}
    for length in range(4):
        result['ascii-prefix-%d' % length] = (HEAD + b'AZZ'[:length], 8, 2,
            {'kind': 'ascii-prefix-witness', 'prefix_bytes': length, 'setup_hex': HEAD.hex()})
    for name, body in {
        'palette-save-rgb-restore-background': C + b'40m' + E + b'7' + C + b'48;2;237;31;126m' + E + b'8X',
        'palette-save-rgb-restore-foreground': C + b'30m' + E + b'7' + C + b'38;2;237;31;126m' + E + b'8X',
        '1049-palette-save-rgb-restore': C + b'40m' + C + b'?1049h' + C + b'48;2;237;31;126m' + C + b'?1049lX',
        'palette-save-rgb-default-restore': C + b'40m' + E + b'7' + C + b'48;2;237;31;126m' + C + b'49m' + E + b'8X',
    }.items():
        result[name] = (HEAD + body, 12, 4, {'kind': 'saved-colour-discriminator'})
    rec = runpy.run_path(str(ROOT / 'tools/corpus/rec.py'))['events']
    for path in sorted((ROOT / 'tests/corpus').glob('*.rec')):
        source = path.read_bytes()
        stream = BytesIO()
        stream.write(b'warren-rec 1\n')
        size = None
        point = 0
        for kind, value in rec(path):
            if kind in ('size', 'r'):
                stream.write(b'%s %d %d\n' % (kind.encode(), *value))
                if kind == 'size':
                    size = value
                else:
                    point += 1
                    data = fixture_input('recordings', stream.getvalue())
                    result['recording-%s-resize-%d' % (path.stem, point)] = (data, *size,
                        {'kind': 'recording-resize-checkpoint', 'recording': path.name, 'resize_index': point,
                         'original_input_sha256': hashlib.sha256(source).hexdigest(), 'target_size': list(value)})
            else:
                stream.write(b'%s %d\n' % (kind.encode(), len(value)) + value + b'\n')
    assert len(result) == 11 and len(result) <= 16
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    selected = cases()
    print('BUNDLE complete-dumps=%d terminal-passes=%d hard-cap=16' % (len(selected), 2 * len(selected)), flush=True)
    if args.list:
        for name in selected:
            print(name)
        return 0
    if not args.out:
        parser.error('--out required unless --list')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'complete_dump_count': len(selected),
                'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
                'cases': {}, 'errors': []}
    with oracle.Display() as display:
        for name, (data, cols, rows, provenance) in selected.items():
            source = args.out / (name + ('.rec' if data.startswith(b'warren-rec 1\n') else '.in'))
            source.write_bytes(data)
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'size': [cols, rows], **provenance}
            try:
                work = args.out / name
                got = oracle.dump(display, source.resolve(), cols, rows, work.resolve())
                encoded = screen.dumps(got).encode()
                (work / 'got.screen').write_bytes(encoded)
                entry.update(screen_sha256=hashlib.sha256(encoded).hexdigest(), classification='measured')
                print('MEASURE %s' % name, flush=True)
            except (oracle.OracleError, ValueError, OSError) as error:
                entry.update(classification='reference-measurement-error', error=str(error))
                manifest['errors'].append(name)
                print('MEASURE-ERROR %s %s' % (name, error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=%d errors=%d' % (len(selected), len(manifest['errors'])), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
