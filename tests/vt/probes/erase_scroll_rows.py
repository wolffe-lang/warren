#!/usr/bin/env python3
"""16 dumps/32 terminal processes: partial ECH after blank-row creation."""
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


def cases():
    bottom = C + b'4;1H'
    scrolled = bottom + b'\n'
    sources = {
        'fresh-top': b'',
        'fresh-bottom': bottom,
        'linefeed-without-scroll': C + b'3;1H\n',
        'linefeed-scroll': scrolled,
        'index-scroll': bottom + E + b'D',
        'next-line-scroll': bottom + E + b'E',
        'scroll-up': C + b'S' + bottom,
        'delete-line': bottom + C + b'M',
        'insert-line': bottom + C + b'L',
        'reverse-index-scroll': E + b'M',
        'scrolled-line-clear': scrolled + C + b'2K',
        'scrolled-reset': scrolled + E + b'c' + HEAD,
        'scrolled-background': scrolled + C + b'42m',
        'scrolled-written-prefix': scrolled + b'abcd',
        'scrolled-move-away-back': scrolled + C + b'1;1H' + bottom,
        'regional-linefeed-scroll': C + b'2;3r' + C + b'?6h' + C + b'2;1H\n',
    }
    assert len(sources) == 16
    return {name: HEAD + prefix + C + b'5G' + C + b'5X' for name, prefix in sources.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'dump_budget': 16, 'terminal_process_budget': 32,
                'cases': {}, 'errors': []}
    print('BUNDLE complete-dumps=16 terminal-processes-at-most=32', flush=True)
    with oracle.Display() as display:
        for name, data in cases().items():
            path = args.out / (name + '.in')
            path.write_bytes(data)
            work = args.out / name
            entry = {'input_sha256': hashlib.sha256(data).hexdigest()}
            try:
                got = oracle.dump(display, path.resolve(), 12, 4, work.resolve())
                text = screen.dumps(got)
                (work / 'got.screen').write_text(text)
                entry['screen_sha256'] = hashlib.sha256(text.encode()).hexdigest()
                entry['cursor'] = got['cursor']
                entry['extents'] = got['extents']
                print('MEASURE %s row=%d extent=%d all=%s' %
                      (name, got['cursor']['row'], got['extents'][got['cursor']['row'] - 1], got['extents']), flush=True)
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
