#!/usr/bin/env python3
"""The fresh drive's known failures, each tracked by an issue, never hidden.

tests/vt/fresh-known.json names each seed whose failure is a known defect: the
issue that tracks it and the failures the seed shows. A listed seed that fails
with exactly those failures prints KNOWN with its issue and does not redden the
drive. A listed seed that passes prints FIXED and fails the drive until it
leaves the list. A listed seed that fails in any other way, and any unlisted
seed that fails, are red as before.
"""
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/vt'))
import fresh_fuzz  # noqa: E402

KNOWN = {'fresh-0007': {'issue': 9999, 'failures': ['R1-R3-R8']}}


def outcome(name, failures, known=KNOWN):
    """The drive's own per-case step on a fresh manifest: what it prints and counts."""
    manifest = {'failed': 0, 'known': {}, 'fixed': {}}
    entry = {'failures': [{'name': failure} for failure in failures], 'reference_exclusion': []}
    printed = io.StringIO()
    with contextlib.redirect_stdout(printed):
        fresh_fuzz.case_outcome(manifest, name, entry, 4096, known)
    return printed.getvalue(), manifest, entry


def main():
    failed = []

    def row(name, check):
        try:
            ok, detail = check()
        except Exception as error:  # a missing step is a red row, by name
            ok, detail = False, '%s: %s' % (type(error).__name__, error)
        if ok:
            print('PASS fresh-known %s' % name, flush=True)
        else:
            print('FAIL fresh-known %s: %r' % (name, str(detail)[:400]), flush=True)
            failed.append(name)

    def known_fails():
        printed, manifest, entry = outcome('fresh-0007', ['R1-R3-R8'])
        return (printed == 'KNOWN fresh-0007 warren#9999 failures=R1-R3-R8\n' and manifest['failed'] == 0
                and manifest['known'] == {'fresh-0007': 9999} and entry['known_issue'] == 9999), (printed, manifest)

    def known_passes():
        printed, manifest, entry = outcome('fresh-0007', [])
        return (printed == 'FIXED fresh-0007 warren#9999 passes: remove it from the list in tests/vt/fresh-known.json\n'
                and manifest['failed'] == 1 and manifest['fixed'] == {'fresh-0007': 9999}
                and manifest['known'] == {}), (printed, manifest)

    def unknown_fails():
        printed, manifest, entry = outcome('fresh-0001', ['P2-bytewise'])
        return (printed == 'FAIL fresh-fuzz fresh-0001 bytes=4096 failures=P2-bytewise reference-excluded=False\n'
                and manifest['failed'] == 1 and manifest['known'] == {} and 'known_issue' not in entry), (printed, manifest)

    def known_fails_otherwise():
        printed, manifest, entry = outcome('fresh-0007', ['R1-R3-R8', 'P2-random'])
        return (printed == 'FAIL fresh-fuzz fresh-0007 bytes=4096 failures=R1-R3-R8,P2-random reference-excluded=False'
                ' known=warren#9999:R1-R3-R8\n' and manifest['failed'] == 1 and manifest['known'] == {}), (printed, manifest)

    def unknown_passes():
        printed, manifest, entry = outcome('fresh-0001', [])
        return (printed == 'PASS fresh-fuzz fresh-0001 bytes=4096 failures=- reference-excluded=False\n'
                and manifest['failed'] == 0), (printed, manifest)

    def list_loads():
        # The repo's own list loads under the same checks the refusals below exercise.
        known = fresh_fuzz.known_failures()
        return isinstance(known, dict), known

    def list_refusals():
        refused = []
        bad = ({'fresh-0000': {'issue': 9999, 'failures': ['R1-R3-R8']}},
               {'fresh-5001': {'issue': 9999, 'failures': ['R1-R3-R8']}},
               {'stream-0001': {'issue': 9999, 'failures': ['R1-R3-R8']}},
               {'fresh-0001': {'issue': 0, 'failures': ['R1-R3-R8']}},
               {'fresh-0001': {'issue': '25', 'failures': ['R1-R3-R8']}},
               {'fresh-0001': {'issue': 9999, 'failures': []}},
               {'fresh-0001': {'issue': 9999, 'failures': ['R1-R3-R8', 'R1-R3-R8']}},
               {'fresh-0001': {'issue': 9999, 'failures': ['reference-terminal-killed']}},
               {'fresh-0001': {'issue': 9999, 'failures': ['R1-R3-R8'], 'note': 'x'}},
               [])
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'known.json'
            for listed in bad:
                path.write_text(json.dumps(listed))
                try:
                    fresh_fuzz.known_failures(path)
                except ValueError:
                    refused.append(True)
                else:
                    refused.append(False)
        return all(refused), refused

    row('known-fails', known_fails)
    row('known-passes', known_passes)
    row('unknown-fails', unknown_fails)
    row('known-fails-otherwise', known_fails_otherwise)
    row('unknown-passes', unknown_passes)
    row('list-loads', list_loads)
    row('list-refusals', list_refusals)
    if failed:
        print('FAIL fresh-known rows: %s' % ' '.join(failed))
        return 1
    print('PASS fresh-known known-quiet fixed-red unknown-red otherwise-red list-checked')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
