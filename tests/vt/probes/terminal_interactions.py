#!/usr/bin/env python3
"""Small pinned-binary interaction measurements; never terminal source reads.

All rows are measurements, not implicit passes. Raw A/S replies and print
bytes are retained alongside each input and canonical dump.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen

E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'
RGB = C + b'38;2;1;2;3;48;2;237;32;126m'
BRIGHT = C + b'1;91;42m'
CASES = {
    'tabs-cleared': C + b'3g',
    'hts-column-one': C + b'3g' + E + b'H',
    'hts-column-two': C + b'3g' + C + b'2G' + E + b'H',
    'rgb-direct': RGB + b'X',
    'rgb-save-restore': RGB + E + b'7' + C + b'0m' + E + b'8X',
    'bright-bold-direct': BRIGHT + b'X',
    'bright-bold-save-restore': BRIGHT + E + b'7' + C + b'0m' + E + b'8X',
    'bright-indexed-bold': C + b'1;38;5;9;42mX',
    'rgb-1049-restore': RGB + C + b'?1049h' + C + b'0m' + C + b'?1049lX',
    '1049-repeat-cycle': b'ab' + C + b'?1049hx' + C + b'?1049hy' + C + b'?1049lZ',
    '1049-inactive-reset-cursor': C + b'3;2H' + C + b'?1049lZ',
    '1049-inactive-reset-background': C + b'48;5;181m' + C + b'?1049l' + C + b'?1049h',
    'ech-to-right-edge': b'abcde' + C + b'1;3H' + C + b'99X',
    'el-to-right-edge': b'abcde' + C + b'1;3H' + C + b'K',
    'dch-to-right-edge': b'abcde' + C + b'1;3H' + C + b'99P',
    'cursor-from-below-region': C + b'2;3r' + C + b'4;1H' + C + b'99A',
    'mouse-reset-other-selector': C + b'?1000h' + C + b'?1002l',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'pins_sha256': digest((ROOT / 'warren-oracle.toml').read_bytes()),
                'cases': {}, 'errors': []}
    with oracle.Display() as display:
        for name, body in CASES.items():
            data = HEAD + body
            source = args.out / (name + '.in')
            source.write_bytes(data)
            work = args.out / name
            entry = {'input_hex': data.hex(), 'input_sha256': digest(data), 'size': [12, 4]}
            try:
                got = oracle.dump(display, source.resolve(), 12, 4, work.resolve())
                encoded = screen.dumps(got).encode()
                (work / 'got.screen').write_bytes(encoded)
                invalid = [(r + 1, c + 1, attrs) for r, row in enumerate(got['rows'])
                           for c, (_, _, attrs) in enumerate(row)
                           if any(int(n) > 255 for n in re.findall(r'(?:fg|bg)=idx:(\d+)', attrs))]
                entry.update(screen_sha256=digest(encoded), cursor=got['cursor'], tabs=got['tabs'],
                             extents=got['extents'], first_cell=got['rows'][0][0],
                             invalid_palette_reports=invalid,
                             classification='reference-report-outside-palette-domain' if invalid else 'measured')
                print('MEASURE %s %s' % (name, entry['classification']), flush=True)
            except (oracle.OracleError, ValueError, OSError) as error:
                entry.update(classification='reference-measurement-error', error=str(error))
                manifest['errors'].append(name)
                print('MEASURE-ERROR %s %s' % (name, error), flush=True)
            manifest['cases'][name] = entry
    (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=%d errors=%d' % (len(CASES), len(manifest['errors'])), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
