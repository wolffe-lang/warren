#!/usr/bin/env python3
"""Reference terminals launched back to back on one display all open it.

The oracle runs one reference terminal at a time, so each is its display's
only client, and a dump's second pass starts the moment its first pass's
terminal exits. An X server resets itself when its last client leaves unless
it is started with -noreset. On hosted runners every retried launch ("Can't
open display") was a second pass, and the same commit retried nothing on one
runner and one launch in twenty on another: the next terminal meeting the
reset, by the machine's timing, is the likely cause. The oracle's display
does not reset between clients.

Two rows. `server-keeps-its-state` reads the arguments the oracle starts its
X server with, from a stand-in on PATH: needs python3 only; it is the row
that is red without -noreset. `back-to-back` launches the pinned terminal on
the oracle's own display, through the oracle's own launch, with no pause,
and holds the retries to none: needs the pinned image. It holds the
behaviour wanted; on the machines tried off the hosted runners it retried
nothing with the reset either. `--unit` runs the first row alone.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle  # noqa: E402

LAUNCHES = 150
FAKE_SERVER = r'''#!/usr/bin/env python3
import os, sys, time
from pathlib import Path
Path(__file__).with_name('argv').write_text('\n'.join(sys.argv[1:]) + '\n')
os.write(int(sys.argv[sys.argv.index('-displayfd') + 1]), b'77\n')
time.sleep(60)
'''


def server_arguments(base):
    """What the oracle's Display starts its X server with."""
    fake = base / 'bin'
    fake.mkdir()
    program = fake / 'Xvfb'
    program.write_text(FAKE_SERVER)
    program.chmod(0o755)
    saved, had = os.environ['PATH'], os.environ.pop('WARREN_ORACLE_DISPLAY', None)
    os.environ['PATH'] = str(fake) + os.pathsep + saved
    try:
        with oracle.Display() as display:
            name = display.name
    finally:
        os.environ['PATH'] = saved
        if had is not None:
            os.environ['WARREN_ORACLE_DISPLAY'] = had
    return name, (fake / 'argv').read_text().split()


def back_to_back(base, launches):
    """Launch `launches` terminals on one display with no pause; the display's retries and launches."""
    with oracle.Display() as display:
        env = {'DISPLAY': display.name, 'LC_ALL': 'C.UTF-8', 'PATH': os.environ['PATH'],
               'HOME': str(base), 'TERM': 'xterm-256color'}
        for n in range(launches):
            answers = base / ('answer-%d' % n)
            command = ['xterm', '-fn', 'fixed', '-e', 'sh', '-c', 'echo answered > "$0"', str(answers)]
            done = oracle.launch(display, 'B', command, env, (answers,), 60)
            if done.returncode != 0 or not answers.exists():
                raise oracle.OracleError('launch %d: exit %d: %s' % (n, done.returncode, oracle.clipped(done.stderr)))
            answers.unlink()
        return list(display.retries), display.launches


def main():
    unit = sys.argv[1:] == ['--unit']
    failed = []
    scratch = ROOT / 'target/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix='display-reset-', dir=scratch))
    try:
        name, arguments = server_arguments(base)
        ok = name == ':77' and '-noreset' in arguments
        print('%s display-reset server-keeps-its-state arguments=%s' % ('PASS' if ok else 'FAIL', ' '.join(arguments)),
              flush=True)
        if not ok:
            failed.append('server-keeps-its-state')
        if not unit:
            try:
                retries, launches = back_to_back(base, LAUNCHES)
                detail = 'retries=%d launches=%d' % (len(retries), launches)
                ok = not retries and launches == LAUNCHES
            except (oracle.OracleError, OSError, subprocess.SubprocessError) as error:
                detail, ok = 'error: %s' % str(error)[:300], False
            print('%s display-reset back-to-back %s' % ('PASS' if ok else 'FAIL', detail), flush=True)
            if not ok:
                failed.append('back-to-back')
    finally:
        shutil.rmtree(base)
    if failed:
        print('FAIL display-reset rows: %s' % ' '.join(failed))
        return 1
    print('PASS display-reset %s' % ('server-keeps-its-state' if unit else 'server-keeps-its-state back-to-back'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
