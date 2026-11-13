#!/usr/bin/env python3
"""24 fresh-row frames/48 terminal passes: erased cells across reflow."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'


def cases():
    result = {}
    for background, pen in (('default', C + b'49m'), ('painted', C + b'45m')):
        bodies = {
            'after-last-glyph': b'abcd' + pen + C + b'5X',
            'between-glyphs': b'a' + C + b'10GZ' + pen + C + b'2G' + C + b'8X',
            'whole-row': b'abcd' + pen + C + b'2K',
            'softwrapped-continuation': b'abcdefghijklM' + pen + C + b'1G' + C + b'5X',
        }
        for kind, body in bodies.items():
            # A default pen at resize distinguishes retained paint from a new
            # column merely receiving the current background during widening.
            data = HEAD + body + C + b'49m'
            initial = b'warren-rec 1\nsize 12 4\no %d\n' % len(data) + data + b'\n'
            for phase, sizes in (('before', b''), ('narrowed', b'r 6 8\n'),
                                 ('widened-back', b'r 6 8\nr 12 4\n')):
                name = '%s-%s-%s' % (kind, background, phase)
                result[name] = (initial + sizes, kind, background, phase)
    assert len(result) == 24
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'dump_budget': 24, 'terminal_process_budget': 48,
                'cases': {}, 'errors': []}
    print('BUNDLE fresh-row-complete-dumps=24 terminal-processes-at-most=48', flush=True)
    with oracle.Display() as display:
        for name, (data, kind, background, phase) in cases().items():
            path = args.out / (name + '.rec')
            path.write_bytes(data)
            work = args.out / name
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'kind': kind,
                     'background': background, 'phase': phase}
            try:
                got = oracle.dump(display, path.resolve(), 12, 4, work.resolve())
                text = screen.dumps(got)
                (work / 'got.screen').write_text(text)
                entry.update(screen_sha256=hashlib.sha256(text.encode()).hexdigest(),
                             size=got['size'], cursor=got['cursor'], extents=got['extents'])
                entry['painted_cells'] = [[r + 1, c + 1, cell[2]] for r, row in enumerate(got['rows'])
                                          for c, cell in enumerate(row) if 'bg=' in cell[2]]
                entry['glyph_cells'] = [[r + 1, c + 1, cell[1]] for r, row in enumerate(got['rows'])
                                        for c, cell in enumerate(row) if cell[1] != 'U+0020']
                print('MEASURE %s size=%s cursor=%s extents=%s painted=%d glyphs=%d' %
                      (name, got['size'], got['cursor'], got['extents'],
                       len(entry['painted_cells']), len(entry['glyph_cells'])), flush=True)
            except (oracle.OracleError, ValueError, OSError) as error:
                entry['error'] = str(error)
                manifest['errors'].append(name)
                print('MEASURE-ERROR', name, str(error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=24 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
