#!/usr/bin/env python3
"""24 dumps/48 passes: separate FG/BG setters between restore and inverse."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[3]
for part in ('tools/oracle', 'tools/vt', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle
import screen
from repair_background_fixture import repair
from d9_fixture import background, with_background
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'


def cases():
    prefix = HEAD + E + b'7' + C + b'48;5;181m' + E + b'8'
    setters = {'none': b'', 'fg-basic': b'31', 'fg-bright': b'91', 'fg-indexed': b'38;5;9',
               'fg-rgb': b'38;2;1;2;3', 'fg-default': b'39', 'bg-basic': b'42',
               'bg-bright': b'102', 'bg-indexed': b'48;5;9', 'bg-rgb': b'48;2;1;2;3',
               'bg-default': b'49', 'reset': b'0'}
    return {name: prefix + (C + setter + b'm' if setter else b'') + C + b'27mX'
            for name, setter in setters.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'complete_dump_count': 24, 'terminal_process_budget': 48, 'cases': {}, 'errors': []}
    print('BUNDLE paired-cases=12 complete-dumps=24 terminal-processes-at-most=48', flush=True)
    with oracle.Display() as display:
        for name, data in cases().items():
            repaired, injections = repair(data)
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(),
                     'repaired_sha256': hashlib.sha256(repaired).hexdigest(), 'injections': injections}
            frames = []
            try:
                for label, body in (('original', data), ('repaired', repaired)):
                    source = args.out / (name + '.' + label + '.in')
                    source.write_bytes(body)
                    work = args.out / (name + '.' + label)
                    frame = oracle.dump(display, source.resolve(), 12, 4, work.resolve())
                    text = screen.dumps(frame)
                    (work / 'got.screen').write_text(text)
                    entry[label + '_screen_sha256'] = hashlib.sha256(text.encode()).hexdigest()
                    frames.append(frame)
                old, new = frames
                bounded = copy.deepcopy(old)
                cells = []
                for r, row in enumerate(old['rows']):
                    for c, cell in enumerate(row):
                        before, after = background(cell[2]), background(new['rows'][r][c][2])
                        if before != after:
                            cells.append([r + 1, c + 1, before, after])
                            bounded['rows'][r][c][2] = with_background(cell[2], after)
                entry['background_delta'] = cells
                entry['nonbackground_differences'] = screen.compare(bounded, new)
                print('MEASURE %s BG-delta=%s non-BG=%s' % (name, cells, entry['nonbackground_differences']), flush=True)
            except (oracle.OracleError, ValueError, OSError) as error:
                entry['error'] = str(error)
                manifest['errors'].append(name)
                print('MEASURE-ERROR', name, str(error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS dumps=24 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
