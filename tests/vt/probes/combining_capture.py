#!/usr/bin/env python3
"""Eight binary-only combining-mark dumps: sixteen terminal passes, cap eight."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
sys.path.insert(0, str(ROOT / 'tests/vt'))
import run as oracle
import screen
from combining_cases import cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=False)
    selected = cases()
    assert len(selected) == 8
    print('BUNDLE complete-dumps=8 terminal-passes=16 hard-cap=8', flush=True)
    manifest = {'schema': 1, 'complete_dump_count': 8, 'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(), 'cases': {}, 'errors': []}
    with oracle.Display() as display:
        for name, (data, cols, rows, provenance) in selected.items():
            source = args.out / (name + ('.rec' if data.startswith(b'warren-rec 1\n') else '.in'))
            source.write_bytes(data)
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'size': [cols, rows], **provenance}
            try:
                work = args.out / name
                got = oracle.dump(display, source.resolve(), cols, rows, work.resolve())
                raw = screen.dumps(got).encode()
                (work / 'got.screen').write_bytes(raw)
                entry['screen_sha256'] = hashlib.sha256(raw).hexdigest()
                print('MEASURE %s extent=%s' % (name, got['extents']), flush=True)
            except (oracle.OracleError, ValueError, OSError) as error:
                entry['error'] = str(error)
                manifest['errors'].append(name)
                print('MEASURE-ERROR %s %s' % (name, error), flush=True)
            manifest['cases'][name] = entry
            (args.out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('MEASUREMENTS cases=8 errors=%d' % len(manifest['errors']), flush=True)
    return bool(manifest['errors'])


if __name__ == '__main__':
    raise SystemExit(main())
