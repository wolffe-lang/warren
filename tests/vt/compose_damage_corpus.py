#!/usr/bin/env python3
"""Compose's damage over every owned corpus stream: the damage-limited image equals a full rescan."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
from corpus_properties import encode
from chunking_suite import events
from reference_inputs import inputs, fixture_input


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--suite', choices=('all', 'census', 'recordings', 'fuzz-baseline'), default='all')
    parser.add_argument('--name')
    parser.add_argument('program')
    args = parser.parse_args()
    total = failed = images = 0
    for suite, streams in inputs().items():
        if args.suite not in ('all', suite):
            continue
        for name, (source, replay) in sorted(streams.items()):
            if args.name and args.name != name:
                continue
            protocol, (fed, resizes, _rolling) = encode(events(fixture_input(suite, source), replay))
            got = subprocess.run([args.program], cwd=ROOT, input=protocol, capture_output=True, timeout=300)
            match = re.fullmatch(rb'COMPOSE-DAMAGE-CORPUS bytes=(\d+) resizes=(\d+) images=(\d+)\n', got.stdout)
            good = (got.returncode == 0 and not got.stderr and match is not None and
                    (int(match.group(1)), int(match.group(2))) == (fed, resizes))
            if match:
                images += int(match.group(3))
            total += 1
            failed += not good
            detail = got.stdout.decode(errors='replace').strip().splitlines()[-1:] or ['']
            print('%s compose-damage-corpus %s/%s exit=%d %s' % ('PASS' if good else 'FAIL', suite, name,
                                                             got.returncode, detail[0]), flush=True)
    assert total
    print('COMPOSE-DAMAGE-CORPUS streams=%d images=%d failed=%d' % (total, images, failed))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
