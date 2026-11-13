#!/usr/bin/env python3
"""Eight raw A/S captures (16 processes) for FFFA/FFFB beside FFF9."""
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
    return {'annotation-%04X-%s' % (cp, name): (HEAD + prefix + chr(cp).encode(), cp, name)
            for cp in (0xFFFA, 0xFFFB) for name, prefix in
            (('ascii', b'a'), ('wide', '中'.encode()), ('unwritten', C + b'1;5H'), ('first', b''))}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'cases': {}, 'terminal_process_budget': 16, 'errors': []}
    print('BUNDLE raw-A+S=8 terminal-processes-at-most=16', flush=True)
    with oracle.Display() as display:
        for name, (data, cp, context) in cases().items():
            path = args.out / (name + '.in')
            path.write_bytes(data)
            work = args.out / name
            work.mkdir()
            entry = {'scalar': 'U+%04X' % cp, 'context': context,
                     'input_sha256': hashlib.sha256(data).hexdigest()}
            try:
                a = oracle.run_pass(display, 'A', path.resolve(), 12, 4, work.resolve())
                tails = [[c + 1 for c, checksum in enumerate(row) if checksum == '0000'] for row in a['checksums']]
                assert tails == ([[2], [], [], []] if context == 'wide' else [[], [], [], []])
                layout = work / 'continuation.json'
                layout.write_text(json.dumps(tails))
                s = oracle.run_pass(display, 'S', path.resolve(), 12, 4, work.resolve(), extra=[layout])
                try:
                    frame = oracle.finish(oracle.describe(a), a, s)
                    (work / 'got.screen').write_text(screen.dumps(frame))
                    entry['classification'] = 'complete-reference-frame'
                except (oracle.OracleError, ValueError) as error:
                    entry.update(classification='strict-report-failure', validator_error=str(error))
                print('MEASURE %s CPR=%r A-print=%r class=%s' %
                      (name, a['cpr'], a['print'], entry['classification']), flush=True)
            except (AssertionError, oracle.OracleError, ValueError, OSError) as error:
                entry['error'] = str(error)
                manifest['errors'].append(name)
                print('MEASURE-ERROR', name, str(error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=8 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
