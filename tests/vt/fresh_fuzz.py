#!/usr/bin/env python3
"""Live complete-frame/P2/R1/R3/R8 drive:200 seeds per PR,5000 nightly.

Paired-reference inputs are source-triggered; each permitted field delta and
per-rule case count is retained. Unknown differences stay red. Candidate output
never constructs an expected frame. A case journal survives interrupted takes.
"""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/corpus'))
import fuzz


def generated(count, size):
    if not 1 <= count <= 5000 or not 1 <= size <= 60000:
        raise ValueError('fresh drive requires1..5000 seeds and1..60000 requested bytes')
    return {'fresh-%04d' % seed: fuzz.stream(seed, size) for seed in range(1, count + 1)}


def profile_settings(name):
    profiles = json.loads((ROOT / 'tests/vt/fuzz-tiers.json').read_text())
    if name not in profiles:
        raise ValueError('unknown fresh fuzz profile')
    return profiles[name]['seeds'], profiles[name]['bytes']


def profile_deadline(name):
    """The profile's own bound on a drive, in seconds: twice its seeds at the
    slowest pace measured on hosted runs (ci/tiers.py), so a drive that ends on
    it ran at half that pace and says so by name."""
    profiles = json.loads((ROOT / 'tests/vt/fuzz-tiers.json').read_text())
    if name not in profiles:
        raise ValueError('unknown fresh fuzz profile')
    return profiles[name]['deadline']


KNOWN_LIST = ROOT / 'tests/vt/fresh-known.json'
# The failures a known seed may list: every name the drive gives a case except a
# reference terminal that never opened its display or died on a signal, which
# are retried and rate-bounded, never a seed's own defect.
KNOWN_FAILURE_NAMES = ('reference-observation-or-bound', 'unclassified-complete-frame',
                       'P2-bytewise', 'P2-random', 'R1-R3-R8', 'native-exit')


def known_failures(path=KNOWN_LIST):
    """Seeds whose failure is a known defect, each with the issue that tracks it and
    the failures it shows: {name: {'issue': N, 'failures': [...]}}."""
    listed = json.loads(Path(path).read_text())
    if not isinstance(listed, dict):
        raise ValueError('the known list is an object of seeds')
    for name, entry in listed.items():
        match = re.fullmatch(r'fresh-(\d{4})', name)
        if not match or not 1 <= int(match.group(1)) <= 5000:
            raise ValueError('known seed %r is not fresh-0001..fresh-5000' % name)
        if not isinstance(entry, dict) or set(entry) != {'issue', 'failures'}:
            raise ValueError('known seed %s needs exactly an issue and its failures' % name)
        if type(entry['issue']) is not int or entry['issue'] < 1:
            raise ValueError('known seed %s names no issue' % name)
        failures = entry['failures']
        if (not isinstance(failures, list) or not failures or len(set(failures)) != len(failures)
                or any(failure not in KNOWN_FAILURE_NAMES for failure in failures)):
            raise ValueError('known seed %s lists no failures, a repeated one or an unknown one' % name)
    return listed


def case_outcome(manifest, name, entry, size, known):
    """One case's line and count. A known seed failing exactly as listed is KNOWN and
    does not count; a known seed that passes is FIXED and counts until it leaves the
    list; any other failure counts, as before."""
    failures = [row['name'] for row in entry['failures']]
    listed = known.get(name)
    if listed and failures and sorted(failures) == sorted(listed['failures']):
        entry['known_issue'] = listed['issue']
        manifest['known'][name] = listed['issue']
        print('KNOWN %s warren#%d failures=%s' % (name, listed['issue'], ','.join(failures)), flush=True)
        return
    if listed and not failures:
        manifest['fixed'][name] = listed['issue']
        manifest['failed'] += 1
        print('FIXED %s warren#%d passes: remove it from the list in %s' % (
            name, listed['issue'], KNOWN_LIST.relative_to(ROOT)), flush=True)
        return
    manifest['failed'] += bool(failures)
    line = '%s fresh-fuzz %s bytes=%d failures=%s reference-excluded=%s' % (
        'FAIL' if failures else 'PASS', name, size, ','.join(failures) or '-', bool(entry['reference_exclusion']))
    if listed:
        line += ' known=warren#%d:%s' % (listed['issue'], ','.join(listed['failures']))
    print(line, flush=True)


def failure_name(error):
    """A reference terminal that never opened its display, or died on a signal before
    answering, is not a bound violation: each has its own name."""
    return getattr(error, 'failure_name', 'reference-observation-or-bound')


def note_display_retries(manifest, entry, name, retries):
    """Every retried reference launch is kept by name in its case and in the manifest."""
    entry['display_retries'] = [dict(retry) for retry in retries]
    manifest['display_retries'].extend({'case': name, **retry} for retry in retries)
    return len(retries)


def rate_verdict(manifest, display):
    """The display's retries against its bound: past it, the named FAIL line, counted as a failure."""
    problem = display.rate_problem()
    if problem:
        print('FAIL ' + problem, flush=True)
        manifest['failed'] += 1
        manifest['retry_rate'] = problem
    return problem


def select_cases(cases, names):
    if names is None:
        return cases
    if not names or len(set(names)) != len(names) or any(name not in cases for name in names):
        raise ValueError('diagnostic selection contains duplicate or unknown cases')
    return {name: cases[name] for name in names}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', choices=('pull-request', 'nightly'), default='pull-request')
    parser.add_argument('--seeds', type=int)
    parser.add_argument('--bytes', type=int)
    parser.add_argument('--case', action='append', help='explicit finite diagnostic only; default still runs the full profile')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--deadline', type=float, help="seconds; default the profile's own")
    parser.add_argument('warren')
    parser.add_argument('properties')
    args = parser.parse_args()
    if args.deadline is None:
        args.deadline = profile_deadline(args.profile)
    if not 0 < args.deadline <= 21600:
        parser.error('deadline must be positive and at most 21600 seconds')
    seeds, size = profile_settings(args.profile)
    args.seeds = seeds if args.seeds is None else args.seeds
    args.bytes = size if args.bytes is None else args.bytes
    selected = select_cases(generated(args.seeds, args.bytes), args.case)
    known = known_failures()
    for part in ('tools/oracle', 'tests/vt', 'tools/vt', 'tests/vt/probes'):
        sys.path.insert(0, str(ROOT / part))
    import run as oracle
    import screen
    from origin_fixture import dump as reference_dump
    from chunking_suite import events, encode as chunk_encode
    from corpus_properties import encode as property_encode, observe as property_observe
    from repair_background_fixture import repair as background_input
    from legacy_black_fixture import repair as legacy_input
    from report_fixture import without_bold, tab_operations
    from report_expectations import recompose_no_bold
    from fresh_expectations import background_pair, legacy_pair, measured_tabs, dch_pair
    from dch_tail_fixture import repair as dch_input
    from fresh_reports import status_pass
    from erase_extent_fixture import trace
    args.out.mkdir(parents=True, exist_ok=False)
    rules = ('D7', 'D9', 'D12', 'D13', 'D15', 'RPT-BRIGHT-BOLD-COLOUR', 'RPT-TABS-COLUMN-ONE')
    manifest = {'schema': 2, 'seeds': args.seeds, 'requested_bytes': args.bytes,
        'selected_case_count': len(selected), 'diagnostic_selection': args.case,
        'pins_sha256': hashlib.sha256((ROOT / 'warren-oracle.toml').read_bytes()).hexdigest(),
        'fixture_sha256': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
            ('tests/vt/fresh_expectations.py', 'tests/vt/report_expectations.py',
             'tools/vt/repair_background_fixture.py', 'tools/vt/legacy_black_fixture.py',
             'tools/vt/report_fixture.py', 'tools/vt/erase_extent_fixture.py', 'tools/vt/dch_tail_fixture.py',
             'tests/vt/fresh-known.json')},
        'rule_counts': {rule: {'source_cases': 0, 'cases_with_permitted_delta': 0,
                               'fully_resolved_at_stage': 0} for rule in rules},
        'cases': {}, 'failed': 0, 'known': {}, 'fixed': {}, 'display_retries': []}
    started = time.monotonic()
    source_models = {name: trace(data) for name, data in selected.items()}
    excluded = {name: model['reference_exclusions'] for name, model in source_models.items()
                if model['reference_exclusions']}
    manifest['reference_excluded_cases'] = len(excluded)
    manifest['reference_exclusions'] = excluded
    if len(excluded) > 5:
        manifest.update(held_for_exclusion_count=True, failed=1)
        (args.out / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
        print('FAIL fresh-reference-exclusion-count cases=%d maximum=5' % len(excluded), flush=True)
        return 1
    (args.out / 'header.json').write_text(json.dumps({key: value for key, value in manifest.items() if key != 'cases'}, indent=2) + '\n')
    print('FRESH-DRIVE seeds=%d original-dumps=%d paired-dumps-at-most=%d terminal-processes-at-most=%d excluded-RI-HT-mark=%d P2-strategies=2 resize-paths=4' %
          (args.seeds, len(selected), 3 * len(selected), 9 * len(selected), len(excluded)), flush=True)

    def d7(frame, data):
        result = copy.deepcopy(frame)
        assert result['modes']['synchronized-output'] == '?'
        modes = re.findall(rb'\x1b\[\?2026([hl])', data)
        result['modes']['synchronized-output'] = int(bool(modes) and modes[-1] == b'h')
        return result

    with oracle.Display() as display, (args.out / 'cases.jsonl').open('w') as journal:
        for name, data in selected.items():
            if time.monotonic() - started > args.deadline:
                manifest['deadline_exhausted'] = True
                manifest['failed'] += 1
                break
            work = args.out / name
            work.mkdir()
            source = work / 'input.in'
            source.write_bytes(data)
            entry = {'input_sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data),
                     'failures': [], 'rules': {}, 'reference_exclusion': excluded.get(name, [])}
            written = None
            stages = []
            retries_before = len(display.retries)

            def stage(rule, frame, detail, triggered, changed):
                entry['rules'][rule] = detail
                if triggered:
                    manifest['rule_counts'][rule]['source_cases'] += 1
                if changed:
                    manifest['rule_counts'][rule]['cases_with_permitted_delta'] += 1
                stages.append((rule, d7(frame, data)))
                return frame

            def dump_input(label, body):
                path = work / (label + '.in')
                path.write_bytes(body)
                frame = reference_dump(display, path.resolve(), 80, 24, (work / label).resolve())
                (work / (label + '.screen')).write_text(screen.dumps(frame))
                return frame

            try:
                reference = dump_input('reference', data)
                current = stage('D7', reference, {'mode': 'synchronized-output', 'value': d7(reference, data)['modes']['synchronized-output']}, True, True)
                entry['reference_report_divergences'] = ['D12'] if (work / 'reference/D12.json').exists() else []
                if entry['reference_report_divergences']:
                    manifest['rule_counts']['D12']['source_cases'] += 1
                    manifest['rule_counts']['D12']['cases_with_permitted_delta'] += 1
                    entry['rules']['D12'] = json.loads((work / 'reference/D12.json').read_text())
                if not entry['reference_exclusion']:
                    current_input, injections = background_input(data)
                    if injections:
                        paired = dump_input('background-repaired-reference', current_input)
                        current, detail = background_pair(data, current, paired)
                        stage('D9', current, detail, bool(detail['triggers']), bool(detail['cells']))
                    legacy_fixed, edits = legacy_input(current_input)
                    if edits:
                        paired = dump_input('legacy-black-reference', legacy_fixed)
                        current, detail = legacy_pair(current_input, current, paired)
                        current_input = legacy_fixed
                        stage('D13', current, detail, True, bool(detail['cells']))
                    # D15: a DCH whose vacated span starts on a second half. The
                    # reference blanks the cell that moved in from the last column;
                    # its split input keeps it, and the bound allows that cell only.
                    split_input, edits = dch_input(current_input)
                    if edits:
                        paired = dump_input('dch-split-reference', split_input)
                        current, detail = dch_pair(current_input, current, paired)
                        current_input = split_input
                        stage('D15', current, detail, True, bool(detail['cells']))
                    plain_input, edits = without_bold(current_input)
                    # Stream32's opposite promotion stays explicitly outside
                    # no-bold. Its separate D13 input supplies its complete frame.
                    if edits and name != 'fresh-0032':
                        paired = dump_input('no-bold-reference', plain_input)
                        current, cells = recompose_no_bold(name, current, paired)
                        stage('RPT-BRIGHT-BOLD-COLOUR', current,
                              {'source_edits': edits, 'foreground_cells': [list(cell) for cell in sorted(cells)]}, True, bool(cells))
                    if tab_operations(data):
                        record = status_pass(display, source, work / 'tab-status.json')
                        current, detail = measured_tabs(data, current, record)
                        stage('RPT-TABS-COLUMN-ONE', current, detail, True, detail['tab_one'])
                    # The source trace's cursor must be the reference's: a check
                    # on the reference, never a correction of it. (D14's extent
                    # corrections are withdrawn: with jump scroll off the
                    # reference's extents are warren's contract, warren#25.)
                    traced = source_models[name]['cursor']
                    assert traced == [current['cursor']['row'], current['cursor']['col']], 'source cursor differs from reference DECCIR'
                    written = d7(current, data)
                    (work / 'expected.screen').write_text(screen.dumps(written))
            except (AssertionError, oracle.OracleError, ValueError, OSError, subprocess.TimeoutExpired) as error:
                if entry['reference_exclusion']:
                    entry['excluded_reference_observation_error'] = str(error)
                else:
                    entry['failures'].append({'name': failure_name(error), 'error': str(error)})
                written = None
            command = [args.warren, 'vt-dump', '--history-bytes', '1048576']
            native = subprocess.run(command, input=data, capture_output=True, cwd=ROOT, timeout=30)
            (work / 'native.stdout').write_bytes(native.stdout)
            (work / 'native.stderr').write_bytes(native.stderr)
            if native.returncode or native.stderr:
                entry['failures'].append({'name': 'native-exit', 'exit': native.returncode})
            else:
                actual = screen.loads(native.stdout.decode())
                previous = None
                for rule, frame in stages:
                    differences = screen.compare(frame, actual)
                    if previous and not differences:
                        manifest['rule_counts'][rule]['fully_resolved_at_stage'] += 1
                    previous = differences
                if written is not None:
                    differences = screen.compare(written, actual)
                    if differences:
                        entry['failures'].append({'name': 'unclassified-complete-frame', 'differences': differences})
                stream = events(data, False)
                for strategy in ('bytewise', 'random'):
                    chunked = subprocess.run(command + ['--replay'], input=chunk_encode(stream, strategy),
                                             capture_output=True, cwd=ROOT, timeout=30)
                    if chunked.returncode or chunked.stderr or chunked.stdout != native.stdout:
                        entry['failures'].append({'name': 'P2-' + strategy, 'exit': chunked.returncode})
                        (work / (strategy + '.stdout')).write_bytes(chunked.stdout)
                        (work / (strategy + '.stderr')).write_bytes(chunked.stderr)
                protocol, counts = property_encode(stream)
                result, frame = property_observe(args.properties, protocol, counts)
                if result.returncode or result.stderr or frame != native.stdout:
                    entry['failures'].append({'name': 'R1-R3-R8', 'exit': result.returncode})
                    (work / 'properties.stdout').write_bytes(result.stdout)
                    (work / 'properties.stderr').write_bytes(result.stderr)
            retried = note_display_retries(manifest, entry, name, display.retries[retries_before:])
            if retried:
                print('RETRIED fresh-fuzz %s %s launches=%d %s' % (
                    name, ','.join(sorted({retry['name'] for retry in entry['display_retries']})), retried,
                    ' '.join('%s/%s' % (Path(retry['work']).name, retry['pass'])
                             for retry in entry['display_retries'])), flush=True)
            case_outcome(manifest, name, entry, len(data), known)
            manifest['cases'][name] = entry
            journal.write(json.dumps({'name': name, **entry}) + '\n')
            journal.flush()
            (args.out / 'progress.json').write_text(json.dumps({'completed': len(manifest['cases']), 'failed': manifest['failed']}) + '\n')
    manifest['launches'] = display.launches
    rate_verdict(manifest, display)
    (args.out / 'result.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('FRESH-RULE-COUNTS ' + json.dumps(manifest['rule_counts'], sort_keys=True), flush=True)
    print('FRESH-FUZZ completed=%d requested=%d failed=%d known=%d fixed=%d reference-excluded=%d display-retries=%d launches=%d retry-bound=%d' %
          (len(manifest['cases']), len(selected), manifest['failed'], len(manifest['known']), len(manifest['fixed']), len(excluded),
           len(manifest['display_retries']), display.launches, oracle.retry_bound(display.launches)), flush=True)
    return bool(manifest['failed'])


if __name__ == '__main__':
    raise SystemExit(main())
