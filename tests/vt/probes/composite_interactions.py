#!/usr/bin/env python3
"""Finite composite-failure measurements, operation-boundary prefixes only.

At most 90 complete dumps (180 A/S terminal passes), never an unbounded
search. Prefixes are selected diagnostic hints, not a shortest-prefix claim.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import runpy
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle
import screen
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'
H = C + b'?1049h'
L = C + b'?1049l'
BG = C + b'48;5;181m'
RGB = C + b'48;2;237;31;126m'


def cases():
    result = {}
    for name, body in {
        '1049-repeat-colour': H + BG + H + L + H,
        '1049-repeat-colour-double-reset': H + BG + H + L + L + H,
        '1049-alt-save-colour': H + BG + E + b'7' + L + H,
        '1049-repeat-restore-pen': H + BG + H + L + b'X',
        '1049-alt-save-restore-pen': H + BG + E + b'7' + L + b'X',
        '1049-plain-colour-history': BG + H + L + H,
        '1049-reset-then-47-content': H + b'X' + L + C + b'?47h',
        '1049-repeat-rgb': H + RGB + H + L + H,
        '1049-repeat-rgb-pen': H + RGB + H + L + b'X',
        '1049-repeated-reset-rgb': RGB + H + L + L + H,
        'ich-blank': C + b'5G' + C + b'@',
        'ich-past-extent': b'ab' + C + b'5G' + C + b'@',
        'ich-all-suffix-lost': b'abcde' + C + b'3G' + C + b'99@',
        'ich-partial-suffix-lost': b'abcdefghij' + C + b'3G' + C + b'8@',
        'ich-fills-last-cell': b'abcde' + C + b'3G' + C + b'7@',
        'dch-middle': b'abcde' + C + b'3G' + C + b'P',
        'dch-past-extent': b'ab' + C + b'5G' + C + b'P',
        'ech-past-extent': b'ab' + C + b'5G' + C + b'X',
        'ech-last-content-not-right-edge': b'abcde' + C + b'3G' + C + b'3X',
        'el-wide-tail': 'ab中Z'.encode() + C + b'4G' + C + b'K',
        'ech-wide-tail': 'ab中Z'.encode() + C + b'4G' + C + b'99X',
        'dch-wide-tail': 'ab中Z'.encode() + C + b'4G' + C + b'99P',
    }.items():
        result[name] = (HEAD + body, 12, 4, {'kind': 'discriminator'})
    fuzz = runpy.run_path(str(ROOT / 'tools/corpus/fuzz.py'))['stream']
    for seed in (4, 8, 13, 22, 27, 28, 29, 31):
        data = fuzz(seed, 2048)
        # Every selection ends before or after a complete CSI edit. Nothing
        # cuts UTF-8, OSC, CSI or an ESC sequence in its middle.
        edits = list(re.finditer(rb'\x1b\[[0-9;]*[XKP@]', data))[-2:]
        offsets = {len(data)}
        offsets.update(at for match in edits for at in (match.start(), match.end()))
        for at in sorted(offsets):
            result['seed-%02d-prefix-%04d' % (seed, at)] = (HEAD + data[:at], 80, 24,
                {'kind': 'original-fuzz-prefix', 'seed': seed, 'original_prefix_bytes': at,
                 'original_input_sha256': hashlib.sha256(data).hexdigest()})
    for seed in (16, 19):
        data = fuzz(seed, 2048)
        switches = list(re.finditer(rb'\x1b\[\?1049[hl]', data))
        if seed == 19:
            switches = switches[-2:]
        offsets = {len(data)}
        offsets.update(at for match in switches for at in (match.start(), match.end()))
        for at in sorted(offsets):
            result['seed-%02d-prefix-%04d' % (seed, at)] = (HEAD + data[:at], 80, 24,
                {'kind': 'original-fuzz-prefix', 'seed': seed, 'original_prefix_bytes': at,
                 'original_input_sha256': hashlib.sha256(data).hexdigest()})
    assert len(result) <= 90, 'finite diagnostic bundle exceeds its stated bound'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--list', action='store_true')
    args = parser.parse_args()
    selected = cases()
    print('BUNDLE complete-dumps=%d terminal-passes=%d hard-cap=90' % (len(selected), 2 * len(selected)), flush=True)
    if args.list:
        for name in selected:
            print(name)
        return 0
    if not args.out:
        parser.error('--out required unless --list')
    args.out.mkdir(parents=True, exist_ok=False)
    manifest = {'schema': 1, 'complete_dump_count': len(selected), 'terminal_passes': 2 * len(selected),
                'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
                'setup_hex': HEAD.hex(), 'cases': {}, 'errors': []}
    with oracle.Display() as display:
        for name, (data, cols, rows, provenance) in selected.items():
            source = args.out / (name + '.in')
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
