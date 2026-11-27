#!/usr/bin/env python3
"""warren over ssh on a PAX host, kept inside one directory of the account's: what a script can see with no serial
port and no console.

    remote_rows.py --ssh 'SSH COMMAND' --dir DIR [--dry] [--rows R1,R2,R3,X0]
    remote_rows.py --pax PAX_TREE --warren HOST_WARREN --key KEY --secret FILE ISO WORK

The first form reaches a host that is already up. Every step is one command through SSH COMMAND (split as a shell
splits it; the remote command goes last). The second form boots ISO, an installed-shape image, under QEMU as
burrow_rows.py does, waits for burrowd, and runs the first form against it with the directory /home/pax/warren-rows, once
with --dry and once for real.

On the host it changes nothing outside DIR, which must be an absolute path. Each run makes a directory of its own,
RUN = DIR/run-<UTC time>, and every warren it starts has HOME=RUN/home, XDG_STATE_HOME=RUN/state,
XDG_CONFIG_HOME=RUN/config, WARREN_RUNTIME_DIR=RUN/rt (mode 0700), SHELL=/bin/sh and no XDG_RUNTIME_DIR: its server,
its saved sessions and its configuration are RUN's, never the account's own. It removes nothing. At the end it
stops its own server with kill-server, which keeps the saved files in RUN/state. Outside DIR it only reads (`uname`,
`id -u`, `ls`).

That holds only for a warren that keeps its socket where WARREN_RUNTIME_DIR says. Another one (any warren before
2026-11-14 ignores the variable) would reach the account's own server, and the rows would make a session in it and
then kill it. Two guards stop that before it can happen:
  G0 first, before any warren runs in RUN: `warren list-sessions` with WARREN_RUNTIME_DIR set to a path under RUN
     too long for a socket. A warren that honours the variable refuses it by name, status 1, before dialing
     anything. G0 passes only when the path it names is exactly that one's `default`. Any other answer (`no server
     is running`, a listing, another path) fails G0. R1, R2 and R3 are then skipped (SKIP, not counted), no warren
     verb runs and nothing is killed. X0 still runs.
  R1's socket check: after `new`, RUN/rt/default must be a socket. When it is not, R2 and R3 are skipped and nothing
     is killed. Each kill-server runs behind the same test, in the same command.

The rows also read what an older warren lacks: each pane's working directory in `list --json` (#86), send-keys and
capture-pane (#82), and sessions restored at start (#100). One more guard names such a warren instead of failing
three rows on it:
  G1 after G0, before anything is made: `warren new -A -d`. A warren at or after 0afb88f (2026-11-25, newer than all
     three) refuses it before it dials anything, status 2, `warren: new: -A needs a session name`; an older one
     answers its usage text and starts nothing. Any other answer ends the rows as TOO-OLD G1, naming what they need:
     R1, R2 and R3 are skipped, X0 still runs, and the run exits 3.

  G0 the probe above: nothing is made, dialed or killed
  G1 the probe above: nothing is made, dialed or killed
  R1 `warren new -d -s v5`, run in RUN/work, exits 0, its socket is RUN/rt/default, and `list --json` shows one
     session, v5, with one pane, in RUN/work
  R2 a marker typed into v5's pane with send-keys, and `capture-pane -p -t v5` shows it
  R3 saved sessions within a boot: `kill-server`; `new -d -s probe` says it restored v5, and `list --json` shows v5
     again with its pane in RUN/work (the directory it was made in: a host that reports no pane's later `cd`, with
     no /proc and no OSC 7, still knows that one)
  X0 the account's own warren state has the same names after the rows as before: /run/user/UID/warren,
     /tmp/warren-UID and $HOME/.local/state/warren/sessions (a session the account itself starts or ends during the
     run shows here too)
--dry prints each command it would run, one a line starting `DRY `, and runs none; it prints every command, as if
each guard held. Each row prints PASS, FAIL or SKIP by name (G1 PASS, SKIP or TOO-OLD), then `ROWS-END failed=N`.
G0 and G1 always run, whatever --rows asks. Exit 0 when every asked row passed; 1 when one failed (G0 included);
2 when the run stopped (the host could not be reached, or a bad argument): `ROWS-STOPPED why`, then
`ROWS-END stopped: why`; 3 when the installed warren is too old for the rows: TOO-OLD G1, then `ROWS-END too-old: …`.
"""
import argparse
import json
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--ssh')
ap.add_argument('--dir')
ap.add_argument('--dry', action='store_true')
ap.add_argument('--rows', default='R1,R2,R3,X0')
ap.add_argument('--pax', type=Path)
ap.add_argument('--warren', type=Path)
ap.add_argument('--key', type=Path)
ap.add_argument('--secret', type=Path)
ap.add_argument('iso', nargs='?', type=Path)
ap.add_argument('work', nargs='?', type=Path)
args = ap.parse_args()
ASKED = args.rows.split(',')
OUTSIDE = ('u=$(id -u); for d in /run/user/$u/warren /tmp/warren-$u "$HOME/.local/state/warren/sessions"; do '
           'if [ -e "$d" ]; then echo "$d:"; ls -1A "$d" 2>&1; else echo "$d: absent"; fi; done')


class Remote:
    """Commands on the host through PREFIX, in the run directory RUN; dry: printed, not run."""

    def __init__(self, prefix, base, dry):
        self.prefix = prefix
        self.dry = dry
        self.run = base.rstrip('/') + '/run-' + time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        r = shlex.quote(self.run)
        self.env = (f'unset XDG_RUNTIME_DIR XDG_DATA_HOME; export HOME={r}/home XDG_STATE_HOME={r}/state '
                    f'XDG_CONFIG_HOME={r}/config WARREN_RUNTIME_DIR={r}/rt SHELL=/bin/sh; cd {r}/home && ')

    def raw(self, cmd, tag):
        """CMD as it is, without the run directory's environment (the reads outside DIR, and the run directory's
        own making): its output, or None."""
        return self.call(cmd, tag)

    def inside(self, cmd, tag):
        """CMD in the run directory, with its warren kept there: its output (standard error in it), or None."""
        return self.call(self.env + cmd, tag)

    def call(self, cmd, tag):
        argv = self.prefix + [cmd]
        if self.dry:
            print('DRY ' + shlex.join(argv), flush=True)
            return ''
        try:
            p = subprocess.run(argv, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired:
            print(f'MEASURE {tag}: timed out after 120 s', flush=True)
            return None
        out = p.stdout.decode('utf-8', 'replace').replace('\r', '')
        err = p.stderr.decode('utf-8', 'replace').strip()
        print(f'MEASURE {tag}: status {p.returncode}: ' + ' | '.join(l for l in out.splitlines() if l.strip())
              + (' || stderr: ' + err.replace('\n', ' | ') if err else ''), flush=True)
        return out if p.returncode != 255 else None


def listing(out):
    """The `list --json` object in OUT, or None."""
    for line in (out or '').splitlines():
        if line.startswith('{'):
            try:
                return json.loads(line)
            except ValueError:
                return None
    return None


def panes(obj, name):
    for s in (obj or {}).get('sessions', []):
        if s.get('name') == name:
            return [p for t in s.get('tabs', []) for p in t.get('panes', [])]
    return None


def rows(prefix, base, dry):
    """The rows against the host PREFIX reaches; the number of asked rows that failed (none when dry)."""
    bad = []

    def row(name, ok, what):
        if dry or (name not in ASKED and name not in ('G0', 'G1')):
            return
        print(f'{"PASS" if ok else "FAIL"} {name}: {what}', flush=True)
        if not ok:
            bad.append(name)

    def skip(names, why):
        for name in names:
            if not dry and (name in ASKED or name in ('G0', 'G1')):
                print(f'SKIP {name}: {why}', flush=True)

    h = Remote(prefix, base, dry)
    r = h.run
    print(f'remote_rows: run directory {r}{" (dry)" if dry else ""}', flush=True)
    if h.raw('uname -a; id -u; command -v warren; warren --version 2>&1', 'S0') is None:
        raise SystemExit('the host could not be reached')
    before = h.raw(OUTSIDE, 'X0-before')
    q = shlex.quote
    rt = r + '/rt'
    h.raw(f'mkdir -p {q(r + "/home")} {q(r + "/state")} {q(r + "/config")} {q(r + "/work")} {q(rt)} '
          f'&& chmod 700 {q(rt)} && echo S1 MADE=0', 'S1')

    # G0: a runtime directory under RUN too long for a socket. Only a warren that keeps its socket where
    # WARREN_RUNTIME_DIR says refuses it, by this path, before it dials anything.
    stem = r + '/g0-'
    long = stem + 'x' * max(1, 112 - len(stem + '/default'))
    probe = h.inside(f'WARREN_RUNTIME_DIR={q(long)} warren list-sessions 2>&1; echo G0 STATUS=$?', 'G0') or ''
    st = re.search(r'G0 STATUS=(\d+)', probe)
    named = re.search(r'over the \d+ every host takes: (\S+)', probe)
    g0 = dry or (st is not None and st[1] == '1' and named is not None and named[1] == long + '/default')
    answer = ' | '.join(l for l in probe.splitlines() if l.strip() and not l.startswith('G0 STATUS'))
    row('G0', g0, f'status {st[1] if st else None}; path named {named[1] if named else None}; wanted '
        f'{long}/default; answer: {answer[:200]}')
    ours = False
    old = False
    if not g0:
        skip(('G1', 'R1', 'R2', 'R3'), 'G0 failed: this warren may not keep its socket in RUN, so nothing is run')
    else:
        # G1: `new -A` without a name, refused before anything is dialed by a warren at or after 0afb88f; an older
        # one answers its usage text. Either way nothing is made.
        age = h.inside('warren new -A -d 2>&1; echo G1 STATUS=$?', 'G1') or ''
        st1 = re.search(r'G1 STATUS=(\d+)', age)
        old = not dry and not (st1 is not None and st1[1] == '2' and 'warren: new: -A needs a session name' in age)
        said = ' | '.join(l for l in age.splitlines() if l.strip() and not l.startswith('G1 STATUS'))
        if old:
            print(f'TOO-OLD G1: the installed warren answers `new -A -d` with status {st1[1] if st1 else None} '
                  f'({said[:120]}), not `warren: new: -A needs a session name`: it is older than 0afb88f '
                  f'(2026-11-25), and these rows need each pane\'s directory in list --json (#86), send-keys and '
                  f'capture-pane (#82) and sessions restored at start (#100)', flush=True)
            skip(('R1', 'R2', 'R3'), 'the installed warren is too old for these rows (TOO-OLD G1)')
        else:
            row('G1', True, 'status 2: warren: new: -A needs a session name')
    if g0 and not old:
        made = h.inside(f'cd {q(r + "/work")} && warren new -d -s v5 2>&1; echo R1 NEW=$?; '
                        f'test -S {q(rt + "/default")} && echo R1 SOCKET=yes || echo R1 SOCKET=no', 'R1') or ''
        ours = dry or 'R1 SOCKET=yes' in made
        p1 = panes(listing(h.inside('warren list --json 2>&1', 'R1-list')), 'v5') if ours else None
        one = listing(h.inside('warren list --json 2>&1', 'R1-again')) if ours else None
        names = [s.get('name') for s in (one or {}).get('sessions', [])]
        row('R1', 'R1 NEW=0' in made and ours and names == ['v5'] and p1 is not None and len(p1) == 1
            and p1[0].get('cwd') == r + '/work',
            f'new exit 0: {"R1 NEW=0" in made}; socket {rt}/default: {ours}; sessions {names}; '
            f'panes {len(p1) if p1 else 0}; cwd {p1[0].get("cwd") if p1 else None}')
        if not ours:
            skip(('R2', 'R3'), f'no socket at {rt}/default: the server is not RUN\'s, so nothing is sent or killed')

    if ours:
        n = 1000 + int(time.time()) % 9000
        mark = f'R-{n + 1}'
        h.inside(f"warren send-keys -t v5 'echo R-$(({n}+1))' Enter 2>&1", 'R2-keys')
        seen = False
        for _ in range(1 if dry else 10):
            seen = mark in (h.inside('warren capture-pane -p -t v5 2>&1', 'R2-capture') or '').splitlines()
            if seen:
                break
            time.sleep(0.5)
        row('R2', seen, f'capture-pane shows {mark}: {seen}')

        time.sleep(0 if dry else 1.5)
        live = f'test -S {q(rt + "/default")} && '
        stopped = h.inside(live + 'warren kill-server 2>&1; echo R3 KILL=$?', 'R3-kill') or ''
        again = h.inside('warren new -d -s probe 2>&1; echo R3 NEW=$?', 'R3-new') or ''
        p3 = panes(listing(h.inside('warren list --json 2>&1', 'R3-after')), 'v5')
        restored = bool(re.search(r'restored 1 saved session: v5', again))
        kept = bool(p3) and p3[0].get('cwd') == r + '/work'
        row('R3', 'R3 KILL=0' in stopped and 'R3 NEW=0' in again and restored and kept,
            f'kill-server exit 0: {"R3 KILL=0" in stopped}; restored v5 said: {restored}; v5 back in {r}/work: {kept}')

        h.inside(live + 'warren kill-server 2>&1; echo END KILL=$?', 'S2')
    after = h.raw(OUTSIDE, 'X0-after')
    row('X0', before is not None and before == after, 'the account\'s own warren state ' +
        ('unchanged' if before == after else f'before: {" | ".join((before or "?").splitlines())}; after: '
         f'{" | ".join((after or "?").splitlines())}'))
    return len(bad), old


def qemu_proof():
    """Boot ISO under QEMU, wait for burrowd, and run the rows against it, dry and then for real."""
    WORK = args.work.resolve()
    WORK.mkdir(parents=True, exist_ok=False)
    raw = WORK / 'console-bios.serial'
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    com = WORK / 'com1.sock'
    argv = [str(args.pax / 'tools/qemu-run'), '--firmware', 'bios', '--accel', 'kvm', '--timeout', '900',
            '--serial-chardev', f'socket,path={com},server=on,wait=on', str(args.iso.resolve()), '--', '-m', '2048M',
            '-netdev', f'user,id=n0,hostfwd=tcp:127.0.0.1:{port}-:22', '-device', 'virtio-net-pci,netdev=n0']
    print('qemu-run: ' + ' '.join(argv), flush=True)
    q = subprocess.Popen(argv, cwd=args.pax, stdin=subprocess.DEVNULL, stdout=open(WORK / 'qemu.out', 'wb'),
                         stderr=subprocess.STDOUT)
    c = None
    try:
        t0 = time.monotonic()
        while not com.exists() and time.monotonic() - t0 < 30:
            time.sleep(0.1)
        c = socket.socket(socket.AF_UNIX)
        c.connect(str(com))
        got = b''
        end = time.monotonic() + 300
        while b'burrowd: host key' not in got and time.monotonic() < end and q.poll() is None:
            c.settimeout(0.5)
            try:
                b = c.recv(65536)
            except socket.timeout:
                b = b''
            got += b
            with open(raw, 'ab') as f:
                f.write(b)
        if b'burrowd: host key' not in got:
            raise SystemExit('no burrowd host key line')
        ssh = shutil.which('ssh')
        if ssh is None:
            raise SystemExit('no ssh on PATH')
        prefix = [ssh, '-p', str(port), '-i', str(args.key), '-o', 'StrictHostKeyChecking=no', '-o',
                  'UserKnownHostsFile=/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o',
                  'LogLevel=ERROR', 'pax@127.0.0.1']
        end = time.monotonic() + 60
        while time.monotonic() < end:
            if subprocess.run(prefix + ['true'], capture_output=True, timeout=60).returncode == 0:
                break
            time.sleep(5)
        rows(prefix, '/home/pax/warren-rows', True)
        return rows(prefix, '/home/pax/warren-rows', False)
    finally:
        if c is not None:
            c.close()
        q.terminate()
        try:
            q.wait(20)
        except subprocess.TimeoutExpired:
            q.kill()


rc = 2
failed = 0
old = False
stopped = ''
try:
    if args.pax is not None:
        if args.iso is None or args.work is None or args.key is None:
            raise SystemExit('--pax needs ISO, WORK and --key')
        failed, old = qemu_proof()
    else:
        if not args.ssh or not args.dir:
            raise SystemExit('give --ssh and --dir (or --pax and an image)')
        if not args.dir.startswith('/') or '/../' in args.dir + '/' or args.dir.rstrip('/') == '':
            raise SystemExit(f'--dir {args.dir} is not an absolute directory of its own')
        failed, old = rows(shlex.split(args.ssh), args.dir, args.dry)
    rc = 1 if failed else (3 if old else 0)
except SystemExit as e:
    stopped = str(e) or 'stopped'
    print(f'ROWS-STOPPED {stopped}', flush=True)
if stopped:
    print(f'ROWS-END stopped: {stopped}', flush=True)
elif old and not failed:
    print('ROWS-END too-old: the installed warren is older than 0afb88f (2026-11-25); nothing past G1 ran', flush=True)
else:
    print(f'ROWS-END failed={failed}', flush=True)
sys.exit(rc)
