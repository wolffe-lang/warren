#!/usr/bin/env python3
"""A reference terminal that cannot open its display is retried once, by name.

The fake terminal below stands in for the pinned emulator on PATH. It never
opens a display; each launch follows the next action in its plan. Only a
launch that produced no answers and reports the display failure is retried,
once; a terminal that ran and disagreed is never retried, and stderr keeps
both its head and its tail.
"""
import json
import os
from pathlib import Path
import runpy
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle  # noqa: E402

DISPLAY_LINE = "xterm: Xt error: Can't open display: %s\n"
FAKE = r'''
import json, sys
from pathlib import Path
here = Path(__file__).resolve().parent
argv = sys.argv[1:]
inner = argv[argv.index('-e') + 1:]
answers = Path(inner[inner.index('--out') + 1]) if '--out' in inner else Path(inner[5])
count = int((here / 'launches').read_text()) + 1 if (here / 'launches').exists() else 1
(here / 'launches').write_text(str(count))
plan = json.loads((here / 'plan.json').read_text())
action = plan[count - 1] if count <= len(plan) else 'unplanned'
head = 'HEAD-MARKER ' + 'h' * 700 + '\n'
if action == 'display':
    sys.stderr.write(head + "xterm: Xt error: Can't open display: %s\n")
    sys.exit(1)
if action == 'display-answered':
    answers.write_text(json.dumps({'fake': 'answered', 'launch': count}))
    sys.stderr.write("xterm: Xt error: Can't open display: %s\n")
    sys.exit(1)
if action == 'ok':
    answers.write_text(json.dumps({'fake': 'ok', 'launch': count}))
    sys.exit(0)
if action == 'disagree':
    answers.write_text(json.dumps({'error': 'fake terminal disagreed'}))
    sys.exit(0)
sys.stderr.write(head + 'middle ' + 'm' * 700 + '\nTAIL-MARKER ' + action + '\n')
sys.exit(3)
'''


class Fake:
    def __init__(self, base, plan):
        self.dir = base / ('fake-%d' % len(list(base.iterdir())))
        self.bin = self.dir / 'bin'
        self.bin.mkdir(parents=True)
        (self.dir / 'plan.json').write_text(json.dumps(plan))
        script = self.dir / 'fake_terminal.py'
        script.write_text(FAKE)
        wrapper = self.bin / 'xterm'
        wrapper.write_text('#!/bin/sh\nexec "%s" -I "%s" "$@"\n' % (sys.executable, script))
        wrapper.chmod(0o755)
        self.work = self.dir / 'work'
        self.work.mkdir()

    def launches(self):
        path = self.dir / 'launches'
        return int(path.read_text()) if path.exists() else 0


def display():
    shown = oracle.Display()
    shown.name = ':fake'
    return shown


def retries(shown):
    return list(getattr(shown, 'retries', []))


def attempt(fake, shown, which='A'):
    source = fake.dir / 'input.in'
    source.write_bytes(b'abc')
    saved = os.environ['PATH']
    os.environ['PATH'] = str(fake.bin) + os.pathsep + saved
    try:
        return oracle.run_pass(shown, which, source, 12, 4, fake.work), None
    except oracle.OracleError as error:
        return None, error
    finally:
        os.environ['PATH'] = saved


def main():
    oracle.RETRY_PAUSE_SECONDS = 0
    scratch = ROOT / 'target/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix='display-retry-', dir=scratch))
    failed = []

    def row(name, ok, detail):
        if ok:
            print('PASS display-retry %s' % name, flush=True)
        else:
            # One line per red row: the detail is quoted, never a raw multi-line stderr.
            print('FAIL display-retry %s: %r' % (name, detail[:400]), flush=True)
            failed.append(name)

    try:
        fake, shown = Fake(base, ['display', 'ok']), display()
        result, error = attempt(fake, shown)
        found = retries(shown)
        row('once-then-answers', error is None and result and result.get('launch') == 2 and fake.launches() == 2
            and len(found) == 1 and found[0].get('name') == 'reference-display-unavailable' and found[0].get('pass') == 'A',
            'launches=%d retries=%r error=%s' % (fake.launches(), found, error))

        fake, shown = Fake(base, ['display', 'display', 'ok']), display()
        result, error = attempt(fake, shown, 'S')
        text = str(error)
        row('twice-stays-red', result is None and fake.launches() == 2 and len(retries(shown)) == 1
            and isinstance(error, getattr(oracle, 'DisplayUnavailable', ())) and text.startswith('reference-display-unavailable')
            and 'HEAD-MARKER' in text and "Can't open display" in text,
            'launches=%d retries=%d error=%s' % (fake.launches(), len(retries(shown)), text[:160]))

        fake, shown = Fake(base, ['disagree', 'ok']), display()
        result, error = attempt(fake, shown)
        row('disagreement-never-retried', result is None and fake.launches() == 1 and not retries(shown)
            and 'fake terminal disagreed' in str(error) and not str(error).startswith('reference-display-unavailable'),
            'launches=%d error=%s' % (fake.launches(), error))

        fake, shown = Fake(base, ['exit', 'ok']), display()
        result, error = attempt(fake, shown)
        text = str(error)
        row('other-exit-never-retried-head-and-tail', result is None and fake.launches() == 1 and not retries(shown)
            and 'HEAD-MARKER' in text and 'TAIL-MARKER exit' in text and not text.startswith('reference-display-unavailable'),
            'launches=%d error=%s' % (fake.launches(), text[:160]))

        fake, shown = Fake(base, ['display-answered', 'ok']), display()
        result, error = attempt(fake, shown)
        row('answered-launch-never-retried', result is None and fake.launches() == 1 and not retries(shown),
            'launches=%d error=%s' % (fake.launches(), error))

        reports = runpy.run_path(str(ROOT / 'tests/vt/probes/fresh_reports.py'))
        fake, shown = Fake(base, ['display', 'ok']), display()
        saved = os.environ['PATH']
        os.environ['PATH'] = str(fake.bin) + os.pathsep + saved
        try:
            source = fake.dir / 'tabs.in'
            source.write_bytes(b'\x1bH')
            status, error = reports['status_pass'](shown, source, fake.work / 'tab-status.json'), None
        except (AssertionError, oracle.OracleError) as caught:
            status, error = None, caught
        finally:
            os.environ['PATH'] = saved
        found = retries(shown)
        row('status-pass-once-then-answers', error is None and status and status.get('launch') == 2 and fake.launches() == 2
            and len(found) == 1 and found[0].get('pass') == 'status',
            'launches=%d retries=%r error=%s' % (fake.launches(), found, error))

        fresh = runpy.run_path(str(ROOT / 'tests/vt/fresh_fuzz.py'))
        name_of = fresh.get('failure_name')
        unavailable = getattr(oracle, 'DisplayUnavailable', None)
        row('fresh-failure-names', name_of is not None and unavailable is not None
            and name_of(unavailable('reference-display-unavailable: pass S')) == 'reference-display-unavailable'
            and name_of(oracle.OracleError('pass S: row 1 differs')) == 'reference-observation-or-bound'
            and name_of(AssertionError('bound')) == 'reference-observation-or-bound',
            'failure_name=%r DisplayUnavailable=%r' % (name_of, unavailable))

        note = fresh.get('note_display_retries')
        manifest, entry = {'display_retries': []}, {}
        counted = note(manifest, entry, 'fresh-0123', [{'name': 'reference-display-unavailable', 'pass': 'S', 'work': 'w'}]) if note else None
        row('fresh-manifest-counts-by-name', counted == 1 and entry.get('display_retries') == [{'name': 'reference-display-unavailable', 'pass': 'S', 'work': 'w'}]
            and manifest['display_retries'] == [{'case': 'fresh-0123', 'name': 'reference-display-unavailable', 'pass': 'S', 'work': 'w'}],
            'note_display_retries=%r counted=%r manifest=%r' % (note, counted, manifest))
    finally:
        shutil.rmtree(base)
    if failed:
        print('FAIL display-retry rows: %s' % ' '.join(failed))
        return 1
    print('PASS display-retry once-only named counted head-and-tail never-on-disagreement')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
