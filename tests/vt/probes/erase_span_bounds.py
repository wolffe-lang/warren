#!/usr/bin/env python3
"""16 dumps/32 passes: bound scroll-row erasure by span and measure reflow."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen
C = b'\x1b['
E = b'\x1b'
HEAD = E + b']2;probe\x07' + C + b'2 q'
ERASE = C + b'5G' + C + b'5X'


def recording(data, resize):
    return b'warren-rec 1\nsize 12 4\no %d\n' % len(data) + data + b'\n' + (b'r 6 8\n' if resize else b'')


def cases():
    scroll = HEAD + C + b'45m' + C + b'4;1H\n'
    selected = {'same-background': scroll + ERASE}
    for label, column in (('before', 4), ('first', 5), ('last', 9), ('after', 10)):
        prefix = scroll + C + str(column).encode() + b'GX'
        selected['print-' + label] = prefix + ERASE
        if label in ('first', 'last'):
            selected['print-' + label + '-then-trim-last'] = prefix + ERASE + C + b'9G' + C + b'K'
    for label, column in (('first', 5), ('last', 9)):
        selected['background-' + label] = scroll + C + str(column).encode() + b'G' + C + b'46m' + C + b'X' + C + b'45m' + ERASE
    selected['changed-pen-background'] = scroll + C + b'42m' + ERASE
    result = {name: (data, False) for name, data in selected.items()}
    for name, prefix in (
        ('scroll-default', HEAD + C + b'4;1H\nabcd'),
        ('scroll-background', scroll + b'abcd'),
        ('fresh-background', HEAD + C + b'45m' + C + b'4;1Habcd')):
        for resized in (False, True):
            result[name + ('-resized' if resized else '-before')] = (recording(prefix + ERASE, resized), True)
    assert len(result) == 16
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'dump_budget': 16, 'terminal_process_budget': 32,
                'cases': {}, 'errors': []}
    print('BUNDLE complete-dumps=16 terminal-processes-at-most=32', flush=True)
    with oracle.Display() as display:
        for name, (data, replay) in cases().items():
            path = args.out / (name + ('.rec' if replay else '.in'))
            path.write_bytes(data)
            work = args.out / name
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'replay': replay}
            try:
                got = oracle.dump(display, path.resolve(), 12, 4, work.resolve())
                text = screen.dumps(got)
                (work / 'got.screen').write_text(text)
                entry['screen_sha256'] = hashlib.sha256(text.encode()).hexdigest()
                entry['size'] = got['size']
                entry['extents'] = got['extents']
                entry['background_cells'] = [[r + 1, c + 1, cell[2]]
                    for r, row in enumerate(got['rows']) for c, cell in enumerate(row) if 'bg=' in cell[2]]
                print('MEASURE %s size=%s extents=%s background-cells=%s' %
                      (name, got['size'], got['extents'], entry['background_cells']), flush=True)
            except (oracle.OracleError, ValueError, OSError) as error:
                entry['error'] = str(error)
                manifest['errors'].append(name)
                print('MEASURE-ERROR', name, str(error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=16 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
