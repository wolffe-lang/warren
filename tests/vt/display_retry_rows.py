#!/usr/bin/env python3
"""A reference terminal that cannot open its display, or that ends on a signal
before it answers, is retried once, by name; the retries are held to a rate.

The fake terminal below stands in for the pinned emulator on PATH. It never
opens a display; each launch follows the next action in its plan. Only a
launch that produced no answers and either reports the display failure or
died on a signal (a real SIGPIPE: a write to a pipe with no reader) is
retried, once in all; a terminal that ran and disagreed, or answered and then
died, is never retried, and stderr keeps both its head and its tail. More
retries than the display's bound is its own named red, in the oracle's
commands and in the fresh drive.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle  # noqa: E402

DISPLAY_LINE = "xterm: Xt error: Can't open display: %s\n"
FAKE = r'''
import json, os, signal, sys
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
def sigpipe():
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
    r, w = os.pipe()
    os.close(r)
    os.write(w, b'x')
    sys.exit(97)
if action == 'sigpipe':
    sigpipe()
if action == 'answered-sigpipe':
    answers.write_text(json.dumps({'fake': 'answered', 'launch': count}))
    sigpipe()
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

        killed = getattr(oracle, 'ReferenceKilled', ())
        fake, shown = Fake(base, ['sigpipe', 'ok']), display()
        result, error = attempt(fake, shown, 'S')
        found = retries(shown)
        row('signal-once-then-answers', error is None and result and result.get('launch') == 2 and fake.launches() == 2
            and len(found) == 1 and found[0].get('name') == 'reference-terminal-killed' and found[0].get('pass') == 'S',
            'launches=%d retries=%r error=%s' % (fake.launches(), found, error))

        fake, shown = Fake(base, ['sigpipe', 'sigpipe', 'ok']), display()
        result, error = attempt(fake, shown, 'S')
        text = str(error)
        row('signal-twice-stays-red', result is None and fake.launches() == 2 and len(retries(shown)) == 1
            and isinstance(error, killed) and text.startswith('reference-terminal-killed') and 'exit -13' in text,
            'launches=%d retries=%d error=%s' % (fake.launches(), len(retries(shown)), text[:160]))

        fake, shown = Fake(base, ['display', 'sigpipe', 'ok']), display()
        result, error = attempt(fake, shown, 'S')
        found = retries(shown)
        row('one-retry-across-causes', result is None and fake.launches() == 2 and len(found) == 1
            and found[0].get('name') == 'reference-display-unavailable' and isinstance(error, killed)
            and str(error).startswith('reference-terminal-killed'),
            'launches=%d retries=%r error=%s' % (fake.launches(), found, str(error)[:160]))

        fake, shown = Fake(base, ['answered-sigpipe', 'ok']), display()
        result, error = attempt(fake, shown, 'S')
        row('signal-after-answers-never-retried', result is None and fake.launches() == 1 and not retries(shown)
            and 'exit -13' in str(error) and not str(error).startswith('reference-terminal-killed'),
            'launches=%d error=%s' % (fake.launches(), error))

        fake, shown = Fake(base, ['display', 'ok', 'display', 'ok', 'display', 'ok']), display()
        for _ in range(3):
            attempt(fake, shown)
        problem = shown.rate_problem() if hasattr(shown, 'rate_problem') else None
        row('rate-bound-over', problem == 'reference-retry-rate retries=3 launches=6 bound=2',
            'launches=%d retries=%d problem=%r' % (fake.launches(), len(retries(shown)), problem))

        fake, shown = Fake(base, ['display', 'ok', 'sigpipe', 'ok', 'ok']), display()
        for _ in range(3):
            attempt(fake, shown)
        problem = shown.rate_problem() if hasattr(shown, 'rate_problem') else None
        row('rate-bound-under', problem == '' and getattr(shown, 'launches', None) == 5 and len(retries(shown)) == 2,
            'launches=%r retries=%d problem=%r' % (getattr(shown, 'launches', None), len(retries(shown)), problem))

        fake = Fake(base, ['display'] * 6)
        streams = fake.dir / 'streams'
        streams.mkdir()
        for n in range(3):
            (streams / ('s%d.in' % n)).write_bytes(b'abc')
        env = dict(os.environ, PATH=str(fake.bin) + os.pathsep + os.environ['PATH'], WARREN_ORACLE_DISPLAY=':fake')
        done = subprocess.run([sys.executable, '-I', str(ROOT / 'tools/oracle/run.py'), 'cases', str(streams),
                               '--out', str(fake.dir / 'cases-out')], env=env, capture_output=True, text=True, timeout=120)
        lines = done.stdout.splitlines()
        row('rate-bound-in-cases-command', done.returncode == 1 and fake.launches() == 6
            and 'FAIL reference-retry-rate retries=3 launches=6 bound=2' in lines,
            'exit=%d launches=%d stdout=%r' % (done.returncode, fake.launches(), done.stdout[-300:]))

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
            and name_of(AssertionError('bound')) == 'reference-observation-or-bound'
            and killed != () and name_of(killed('reference-terminal-killed: pass S')) == 'reference-terminal-killed',
            'failure_name=%r DisplayUnavailable=%r' % (name_of, unavailable))

        note = fresh.get('note_display_retries')
        manifest, entry = {'display_retries': []}, {}
        counted = note(manifest, entry, 'fresh-0123', [{'name': 'reference-display-unavailable', 'pass': 'S', 'work': 'w'}]) if note else None
        row('fresh-manifest-counts-by-name', counted == 1 and entry.get('display_retries') == [{'name': 'reference-display-unavailable', 'pass': 'S', 'work': 'w'}]
            and manifest['display_retries'] == [{'case': 'fresh-0123', 'name': 'reference-display-unavailable', 'pass': 'S', 'work': 'w'}],
            'note_display_retries=%r counted=%r manifest=%r' % (note, counted, manifest))

        verdict = fresh.get('rate_verdict')
        shown = display()
        shown.retries = [{'name': 'reference-terminal-killed', 'pass': 'S', 'work': 'w'}] * 3
        shown.launches = 6
        manifest = {'failed': 0}
        printed = io.StringIO()
        with contextlib.redirect_stdout(printed):
            said = verdict(manifest, shown) if verdict else None
        row('fresh-rate-verdict', said == 'reference-retry-rate retries=3 launches=6 bound=2' and manifest['failed'] == 1
            and printed.getvalue() == 'FAIL reference-retry-rate retries=3 launches=6 bound=2\n',
            'rate_verdict=%r said=%r failed=%r printed=%r' % (verdict, said, manifest['failed'], printed.getvalue()))
    finally:
        shutil.rmtree(base)
    if failed:
        print('FAIL display-retry rows: %s' % ' '.join(failed))
        return 1
    print('PASS display-retry once-only named counted head-and-tail never-on-disagreement signal-retried rate-bounded')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
