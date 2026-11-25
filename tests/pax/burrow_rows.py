#!/usr/bin/env python3
"""warren over burrow at PAX's installed shape under QEMU: one account at the console and over ssh.

    burrow_rows.py --pax PAX_TREE --warren HOST_WARREN --key KEY --secret FILE ISO WORK [ROWS]

ISO is an installed-shape image: /bin/login as pid 1 execs /bin/init, which starts burrowd from its boot hook and a
login on the console. The account pax has KEY's public half in its authorized keys; its password is read from FILE
and typed on COM1, never printed or put in an argument vector. PAX_TREE's tools/qemu-run boots ISO (BIOS, KVM,
2 GiB) with COM1 on a socket this script holds and the guest's port 22 forwarded to 127.0.0.1:PORT, an ephemeral
port. The host's OpenSSH client reaches the guest as pax with KEY. HOST_WARREN is warren for this host; its vt-dump
replays a terminal session's bytes into a screen.

The console is typed on COM1. Each command there is put between two lines of its own, TAG-BEGIN and TAG-END, and
its answer is read between them, so the kernel's own lines (`user: ...`) can land anywhere. A terminal session over
ssh (`ssh -tt`) is driven as a terminal: each cursor-position query (ESC[6n) is answered, and each line is typed
only once the shell's prompt is there, as the shell may lose what is typed ahead of its prompt. Its window is set
to 80x24 with stty before warren runs in it.

  W1 the console makes session con and types a marker into its pane with send-keys; over ssh, `warren ls` lists con
     and `warren capture-pane -p -t con` shows the marker: the ssh side reaches the console's server
  W4 over ssh, `warren new -d -s far` exits 0 and makes no /tmp/warren-1000; then the console's `warren ls` lists
     con and far: one server for both sides
  W2 the console attaches to con and stays attached; a terminal session over ssh runs `warren attach -t con`, and
     its screen shows the marker: a client over ssh attached to the console's session
  W3 the prefix (Ctrl-Space) and d in that session: `[detached from con]`, its `warren attach` exits 0, and
     `warren list-sessions` there shows con with 1 attached, the console's client, still attached
They run in that order (W4 before the console attaches). ROWS is a comma list (default all); the setup the asked
rows need runs either way. Each row prints PASS or FAIL by name, then `ROWS-END failed=N`. Exit 0 when every asked
row passed, 1 when one failed, 2 when the boot, the login or ssh could not be reached (`ROWS-STOPPED why`). Run it
from a directory of its own: WORK must not exist.
"""
import argparse
import os
import re
import select
import shutil
import socket
import subprocess
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--pax', required=True, type=Path)
ap.add_argument('--warren', required=True, type=Path)
ap.add_argument('--key', required=True, type=Path)
ap.add_argument('--secret', required=True, type=Path)
ap.add_argument('iso', type=Path)
ap.add_argument('work', type=Path)
ap.add_argument('rows', nargs='?', default='W1,W4,W2,W3')
args = ap.parse_args()
ASKED = args.rows.split(',')
COLS, LINES = 80, 24
WORK = args.work.resolve()
WORK.mkdir(parents=True, exist_ok=False)
raw = WORK / 'console-bios.serial'
raw.write_bytes(b'')
buf = bytearray()
SSH = shutil.which('ssh')
CPR_ANSWER = b'\x1b[1;1R'
ESCAPES = re.compile(rb'\x1b\[[0-9;?<>= ]*[A-Za-z]|\x1b[()][A-Za-z0-9]|\x1b[=>78]|\x1b\][^\x07]*\x07')
bad = []


def row(name, ok, what):
    if name not in ASKED:
        return
    print(f'{"PASS" if ok else "FAIL"} {name} bios: {what}', flush=True)
    if not ok:
        bad.append(name)


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


PORT = free_port()


# ---------------------------------------------------------------- the console


def pump(t):
    end = time.monotonic() + t
    while True:
        c.settimeout(max(0.05, min(0.3, end - time.monotonic())))
        try:
            b = c.recv(65536)
        except socket.timeout:
            b = None
        except OSError:
            return
        if b == b'':
            return
        if b:
            buf.extend(b)
            with open(raw, 'ab') as f:
                f.write(b)
        if time.monotonic() >= end:
            return


def text(since=0):
    return ESCAPES.sub(b'', bytes(buf[since:])).replace(b'\r', b'').decode('utf-8', 'replace')


def until(pattern, timeout, since):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pump(0.3)
        m = re.search(pattern, text(since), re.M)
        if m:
            return m
        if q.poll() is not None:
            return None
    return None


def typed(b):
    """A line through COM1's input, 20 ms a byte."""
    for ch in b:
        c.sendall(bytes([ch]))
        time.sleep(0.02)
        pump(0)


def console(cmd, tag, timeout=30):
    """CMD at the console; its answer, read between the TAG-BEGIN and TAG-END lines, or None if they never came."""
    s = len(buf)
    typed(f'echo {tag}-BEGIN; {cmd}; echo {tag}-END\r'.encode())
    m = until(rf'(?s)^{tag}-BEGIN\n(.*?)^{tag}-END$', timeout, s)
    answer = m[1] if m else None
    print(f'MEASURE console {tag}: ' + ' | '.join(l for l in (answer or '?').splitlines() if l.strip()), flush=True)
    return answer


# ---------------------------------------------------------------- ssh


def ssh_argv(tty, remote=None):
    argv = [SSH, '-p', str(PORT), '-i', str(args.key), '-o', 'StrictHostKeyChecking=no', '-o',
            'UserKnownHostsFile=/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'LogLevel=ERROR']
    argv += ['-tt'] if tty else []
    return argv + ['pax@127.0.0.1'] + ([remote] if remote else [])


def ssh(remote, tag, timeout=60):
    """REMOTE as an ssh command: (status, output), status None when it ran out of time (what it said is kept)."""
    try:
        p = subprocess.run(ssh_argv(False, remote), capture_output=True, timeout=timeout)
        status, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        status, out, err = None, e.stdout or b'', e.stderr or b''
    out = out.decode('utf-8', 'replace').replace('\r', '')
    err = err.decode('utf-8', 'replace').strip()
    print(f'MEASURE ssh {tag}: ' + (f'status {status}' if status is not None else f'timed out after {timeout} s')
          + ': ' + ' | '.join(l for l in out.splitlines() if l.strip())
          + (' || stderr: ' + err.replace('\n', ' | ') if err else ''), flush=True)
    return status, out


class Term:
    """A terminal session over ssh, driven as a terminal: every cursor-position query answered as it comes."""

    def __init__(self, tag):
        self.tag = tag
        self.p = subprocess.Popen(ssh_argv(True), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE)
        self.fds = {self.p.stdout.fileno(): 'out', self.p.stderr.fileno(): 'err'}
        self.out, self.err = b'', b''
        self.answered = 0
        self.mark = 0
        self.raw = WORK / f'ssh-{tag}.bin'

    def pump(self, t):
        end = time.monotonic() + t
        while self.fds:
            left = end - time.monotonic()
            if left <= 0:
                break
            ready, _, _ = select.select(list(self.fds), [], [], min(left, 0.1))
            for fd in ready:
                b = os.read(fd, 65536)
                if not b:
                    del self.fds[fd]
                elif self.fds[fd] == 'out':
                    self.out += b
                else:
                    self.err += b
            queries = self.out.count(b'\x1b[6n')
            if queries > self.answered:
                self.write(CPR_ANSWER * (queries - self.answered))
                self.answered = queries
        self.raw.write_bytes(self.out)

    def write(self, b):
        try:
            self.p.stdin.write(b)
            self.p.stdin.flush()
        except (BrokenPipeError, OSError):
            pass

    def plain(self, since=0):
        return ESCAPES.sub(b'', self.out[since:]).replace(b'\r', b'').decode('utf-8', 'replace')

    def at_prompt(self):
        return self.plain(self.mark).endswith('$ ')

    def until(self, test, timeout):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if test():
                return True
            if not self.fds:
                return test()
            self.pump(0.2)
        return test()

    def line(self, text, timeout=20):
        """TEXT typed once a prompt ends what came after the last line; False if no prompt came."""
        if not self.until(self.at_prompt, timeout):
            return False
        self.mark = len(self.out)
        self.write(text.encode() + b'\n')
        return True

    def keys(self, b):
        self.write(b)
        self.pump(0.3)

    def screen(self):
        """The session's screen now: its bytes so far replayed through HOST_WARREN's emulator, as lines of text."""
        out = subprocess.run([str(args.warren), 'vt-dump', '--cols', str(COLS), '--rows', str(LINES), str(self.raw)],
                             capture_output=True, timeout=60).stdout.decode('utf-8', 'replace')
        lines = [[' '] * COLS for _ in range(LINES)]
        r = 0
        for ln in out.splitlines():
            if ln.startswith('row '):
                r = int(ln.split()[1])
                continue
            m = re.match(r'^(\d+)(?:-(\d+))? (\d) (\S+)', ln)
            if not m or r < 1:
                continue
            a, b, width, chars = int(m[1]), int(m[2] or m[1]), m[3], m[4]
            if width == '0' or chars == '-':
                continue
            ch = ''.join(chr(int(p, 16)) for p in chars.replace('U+', ' ').split('+') if p.strip())
            for col in range(a, b + 1):
                lines[r - 1][col - 1] = ch
        return [''.join(x).rstrip() for x in lines]

    def close(self, timeout=20):
        self.until(lambda: not self.fds, timeout)
        try:
            self.p.stdin.close()
        except OSError:
            pass
        try:
            status = self.p.wait(5)
        except subprocess.TimeoutExpired:
            self.p.kill()
            self.p.wait()
            status = None
        self.raw.write_bytes(self.out)
        print(f'MEASURE ssh {self.tag}: ' + (f'status {status}' if status is not None else 'killed') + ': '
              + ' | '.join(l for l in self.plain().splitlines() if l.strip()), flush=True)
        return status


# ---------------------------------------------------------------- the rows

com = WORK / 'com1.sock'
argv = [str(args.pax / 'tools/qemu-run'), '--firmware', 'bios', '--accel', 'kvm', '--timeout', '900',
        '--serial-chardev', f'socket,path={com},server=on,wait=on', str(args.iso.resolve()), '--', '-m', '2048M',
        '-netdev', f'user,id=n0,hostfwd=tcp:127.0.0.1:{PORT}-:22', '-device', 'virtio-net-pci,netdev=n0']
print('qemu-run: ' + ' '.join(argv), flush=True)
print(f'ssh: {SSH or "none on PATH"}', flush=True)
q = subprocess.Popen(argv, cwd=args.pax, stdin=subprocess.DEVNULL, stdout=open(WORK / 'qemu.out', 'wb'),
                     stderr=subprocess.STDOUT)
c = None
rc = 2
try:
    t0 = time.monotonic()
    while not com.exists() and time.monotonic() - t0 < 30:
        time.sleep(0.1)
    c = socket.socket(socket.AF_UNIX)
    c.connect(str(com))
    if not until(r'^burrowd: host key [^\n]*\n', 300, 0):
        raise SystemExit('no burrowd host key line: ' + text()[-600:])
    if not until(r'login: $', 120, 0):
        raise SystemExit('no login prompt: ' + text()[-600:])
    s = len(buf)
    typed(b'pax\r')
    if not until(r'[Pp]assword: ?$', 20, s):
        raise SystemExit('no password prompt: ' + text(s)[-300:])
    typed(args.secret.read_text().strip().encode() + b'\r')
    if not until(r'\$ $', 30, s):
        raise SystemExit('no prompt after the login: ' + text(s)[-300:])
    if SSH is None:
        raise SystemExit('no ssh on PATH')
    st = None
    end = time.monotonic() + 60
    while time.monotonic() < end:
        st, _ = ssh('echo REACHED', 'S0')
        if st == 0:
            break
        time.sleep(5)
    if st != 0:
        raise SystemExit('ssh did not reach burrowd')

    # The console's session and its marker: the pane's shell prints W-<n>, which no typed line holds.
    n = 1000 + int(time.time()) % 9000
    mark = f'W-{n + 1}'
    console('warren new -d -s con; echo S1 NEW=$?', 'S1')
    console(f"warren send-keys -t con 'echo W-$(({n}+1))' Enter; echo S2 KEYS=$?", 'S2')

    listed, captured = '', ''
    for _ in range(10):
        _, listed = ssh('warren ls; echo W1 LS=$?', 'W1')
        _, captured = ssh('warren capture-pane -p -t con; echo W1 CAP=$?', 'W1-capture')
        if mark in captured.splitlines():
            break
        time.sleep(0.5)
    row('W1', bool(re.search(r'^con: ', listed, re.M)) and mark in captured.splitlines(),
        f'ssh `warren ls` lists con: {bool(re.search(r"^con: ", listed, re.M))}; '
        f'capture-pane shows {mark}: {mark in captured.splitlines()}')

    _, made = ssh('warren new -d -s far; echo W4 NEW=$?; ls -ld /tmp/warren-1000 2>&1; echo W4-END', 'W4')
    tmp = bool(re.search(r'^d\S* .*/tmp/warren-1000$', made, re.M))
    both = console('warren ls; echo W4 LS=$?', 'W4C') or ''
    row('W4', 'W4 NEW=0' in made and not tmp and bool(re.search(r'^con: ', both, re.M))
        and bool(re.search(r'^far: ', both, re.M)),
        f'far made: {"W4 NEW=0" in made}; /tmp/warren-1000 there: {tmp}; the console lists '
        f'{[l.split(":")[0] for l in both.splitlines() if re.match(r"^[a-z]+: ", l)]}')

    # The console attaches and stays attached: nothing more is typed there.
    typed(b'warren attach -t con\r')
    pump(2)
    ssh('warren list-sessions', 'S3')

    term = Term('W2')
    term.line(f'stty cols {COLS} rows {LINES}')
    term.line('warren attach -t con')
    at = len(term.out)
    seen = term.until(lambda: any(mark in ln.split() for ln in term.screen())
                      or term.plain(at).endswith('$ '), 20)
    on_screen = any(mark in ln.split() for ln in term.screen())
    row('W2', on_screen, f'the screen over ssh shows {mark}: {on_screen}')

    detached = ok_status = one_attached = False
    if on_screen:
        term.keys(b'\x00')
        term.keys(b'd')
        detached = term.until(lambda: '[detached from con]' in term.plain(at) and term.plain(at).endswith('$ '), 20)
        term.line('echo W3 ATTACH=$?')
        term.until(lambda: 'W3 ATTACH=' in term.plain(term.mark) and term.at_prompt(), 20)
        ok_status = bool(re.search(r'^W3 ATTACH=0$', term.plain(term.mark), re.M))
        term.line('warren list-sessions; echo W3 LS=$?')
        term.until(lambda: 'W3 LS=' in term.plain(term.mark) and term.at_prompt(), 20)
        one_attached = bool(re.search(r'^con: \S+ \(1 attached\)$', term.plain(term.mark), re.M))
    term.line('exit')
    term.close()
    row('W3', detached and ok_status and one_attached,
        f'[detached from con]: {detached}; attach exit 0: {ok_status}; con with 1 attached after: {one_attached}')
    rc = 1 if bad else 0
except SystemExit as e:
    print(f'ROWS-STOPPED {e}', flush=True)
finally:
    if c is not None:
        c.close()
    q.terminate()
    try:
        q.wait(20)
    except subprocess.TimeoutExpired:
        q.kill()
print(f'ROWS-END failed={len(bad)}', flush=True)
raise SystemExit(rc)
