#!/usr/bin/env python3
"""warren at login on PAX's installed shape under QEMU: what a console login and logout leave of warren's sessions.

    login_rows.py --pax PAX_TREE --warren HOST_WARREN --key KEY --secret FILE [--hook-file PATH] ISO WORK [ROWS]

ISO is an installed-shape image: /bin/login as pid 1 execs /bin/init, which starts burrowd from its boot hook and a
login on the console, and asks `login:` again when the console's shell ends. The account pax logs in on COM1; its
password is read from FILE and typed there, never printed or put in an argument vector. PAX_TREE's tools/qemu-run
boots ISO (BIOS, KVM, 2 GiB) with COM1 on a socket this script holds and the guest's port 22 forwarded to
127.0.0.1:PORT, an ephemeral port, as burrow_rows.py boots it; the host's OpenSSH client reaches the guest as pax
with KEY. HOST_WARREN is taken as burrow_rows.py takes it, so one launcher runs both files. PATH is the per-user
file the image's /etc/shrc runs at a login (default `$HOME/.config/pelt/shrc`, expanded by the guest's shell).

The console is typed on COM1. Each command there is put between two lines of its own, TAG-BEGIN and TAG-END, and
its answer is read between them, so the kernel's own lines (`user: ...`) can land anywhere.

  L1 a server started at the console outlives that console's logout: `warren new -d -s main` and a marker typed into
     its pane with send-keys; `exit`, and `login:` again; after a new login, `warren ls` lists main, `capture-pane
     -p -t main` still shows the marker, and nothing said `restored`. The marker is what tells the same server from
     a new one that restored main from its saved file, with an empty pane.
  C11 warren started at login: the documented line, `[ -z "$WARREN" ] && [ -t 0 ] && exec warren new -A -s main`,
     written into PATH at the console; after `exit` and a new login, the console is warren's client in session main
     (over ssh, `warren list-sessions` shows main with 1 attached); a marker goes into main's pane; over ssh,
     `warren detach -t main` ends that client and with it the login shell it replaced, and `login:` is asked again;
     after one more login, main has 1 attached again and its pane still shows the marker: the same main. It fails
     on an image whose /etc/shrc does not run PATH.
ROWS is a comma list (default all). Each row prints PASS or FAIL by name, then `ROWS-END failed=N`. Exit 0 when every
asked row passed, 1 when one failed, 2 when the boot or the login could not be reached (`ROWS-STOPPED why`). Run it
from a directory of its own: WORK must not exist.
"""
import argparse
import re
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
ap.add_argument('--hook-file', default='$HOME/.config/pelt/shrc')
ap.add_argument('iso', type=Path)
ap.add_argument('work', type=Path)
ap.add_argument('rows', nargs='?', default='L1,C11')
args = ap.parse_args()
ASKED = args.rows.split(',')
WORK = args.work.resolve()
WORK.mkdir(parents=True, exist_ok=False)
raw = WORK / 'console-bios.serial'
raw.write_bytes(b'')
buf = bytearray()
SSH = shutil.which('ssh')
HOOK_LINE = '[ -z "$WARREN" ] && [ -t 0 ] && exec warren new -A -s main'
ESCAPES = re.compile(rb'\x1b\[[0-9;?<>= ]*[A-Za-z]|\x1b[()][A-Za-z0-9]|\x1b[=>78]|\x1b\][^\x07]*\x07')
bad = []


def free_port():
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]
    s.close()
    return p


PORT = free_port()


def row(name, ok, what):
    if name not in ASKED:
        return
    print(f'{"PASS" if ok else "FAIL"} {name} bios: {what}', flush=True)
    if not ok:
        bad.append(name)


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


def ssh(remote, tag, timeout=60):
    """REMOTE as an ssh command: (status, output), status None when it ran out of time (what it said is kept)."""
    argv = [SSH, '-p', str(PORT), '-i', str(args.key), '-o', 'StrictHostKeyChecking=no', '-o',
            'UserKnownHostsFile=/dev/null', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=20', '-o', 'LogLevel=ERROR',
            'pax@127.0.0.1', remote]
    try:
        p = subprocess.run(argv, capture_output=True, timeout=timeout)
        status, out, err = p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired as e:
        status, out, err = None, e.stdout or b'', e.stderr or b''
    out = out.decode('utf-8', 'replace').replace('\r', '')
    err = err.decode('utf-8', 'replace').strip()
    print(f'MEASURE ssh {tag}: ' + (f'status {status}' if status is not None else f'timed out after {timeout} s')
          + ': ' + ' | '.join(l for l in out.splitlines() if l.strip())
          + (' || stderr: ' + err.replace('\n', ' | ') if err else ''), flush=True)
    return status, out


def attached_main(tag, tries=15):
    """Whether, over ssh, `warren list-sessions` shows main with 1 attached, asked once a second."""
    for _ in range(tries):
        _, out = ssh('warren list-sessions', tag)
        if re.search(r'^main: \S+ \(1 attached\)$', out, re.M):
            return True
        time.sleep(1)
    return False


def login_to_hook(since):
    """Log in as pax at the `login:` asked after SINCE, where the hook may put warren in the shell's place: True
    when a shell's prompt came instead."""
    if not until(r'login: $', 120, since):
        raise SystemExit('no login prompt: ' + text(since)[-600:])
    s = len(buf)
    typed(b'pax\r')
    if not until(r'[Pp]assword: ?$', 20, s):
        raise SystemExit('no password prompt: ' + text(s)[-300:])
    s = len(buf)
    typed(args.secret.read_text().strip().encode() + b'\r')
    pump(5)
    return text(s).endswith('$ ')


def login(since):
    """Log in as pax at the `login:` asked after SINCE; True at a prompt."""
    if not until(r'login: $', 120, since):
        raise SystemExit('no login prompt: ' + text(since)[-600:])
    s = len(buf)
    typed(b'pax\r')
    if not until(r'[Pp]assword: ?$', 20, s):
        raise SystemExit('no password prompt: ' + text(s)[-300:])
    typed(args.secret.read_text().strip().encode() + b'\r')
    if not until(r'\$ $', 30, s):
        raise SystemExit('no prompt after the login: ' + text(s)[-300:])


com = WORK / 'com1.sock'
argv = [str(args.pax / 'tools/qemu-run'), '--firmware', 'bios', '--accel', 'kvm', '--timeout', '900',
        '--serial-chardev', f'socket,path={com},server=on,wait=on', str(args.iso.resolve()), '--', '-m', '2048M',
        '-netdev', f'user,id=n0,hostfwd=tcp:127.0.0.1:{PORT}-:22', '-device', 'virtio-net-pci,netdev=n0']
print('qemu-run: ' + ' '.join(argv), flush=True)
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
    login(0)

    # L1: the marker is printed by the pane's shell, so no typed line holds it.
    n = 1000 + int(time.time()) % 9000
    mark = f'L-{n + 1}'
    console('warren new -d -s main; echo L1A NEW=$?', 'L1A')
    console(f"warren send-keys -t main 'echo L-$(({n}+1))' Enter; echo L1B KEYS=$?", 'L1B')
    before = ''
    for _ in range(10):
        before = console('warren capture-pane -p -t main; echo L1C CAP=$?', 'L1C') or ''
        if mark in before.splitlines():
            break
        time.sleep(0.5)
    s = len(buf)
    typed(b'exit\r')
    asked_again = until(r'login: $', 60, s) is not None
    login(s)
    listed = console('warren ls; echo L1D LS=$?', 'L1D') or ''
    after = console('warren capture-pane -p -t main; echo L1E CAP=$?', 'L1E') or ''
    restored = 'restored' in listed or 'restored' in after
    row('L1', mark in before.splitlines() and asked_again and bool(re.search(r'^main: ', listed, re.M))
        and mark in after.splitlines() and not restored,
        f'{mark} in main before the logout: {mark in before.splitlines()}; login asked again: {asked_again}; '
        f'main listed after: {bool(re.search(r"^main: ", listed, re.M))}; {mark} kept: {mark in after.splitlines()}; '
        f'a restore said: {restored}')

    if 'C11' in ASKED:
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
        hook = console(f"h=\"{args.hook_file}\"; mkdir -p \"${{h%/*}}\" && printf '%s\\n' '{HOOK_LINE}' > \"$h\" "
                       f"&& cat \"$h\"; echo C11A HOOK=$?", 'C11A') or ''
        written = HOOK_LINE in hook.splitlines()
        s = len(buf)
        typed(b'exit\r')
        prompt = login_to_hook(s)
        first = attached_main('C11B')
        n = 1000 + int(time.time()) % 9000
        mark = f'C-{n + 1}'
        ssh(f"warren send-keys -t main 'echo C-$(({n}+1))' Enter", 'C11C')
        seen = False
        for _ in range(10):
            _, cap = ssh('warren capture-pane -p -t main', 'C11D')
            seen = mark in cap.splitlines()
            if seen:
                break
            time.sleep(0.5)
        s = len(buf)
        ssh('warren detach -t main; echo C11E DETACH=$?', 'C11E')
        asked_again = until(r'login: $', 30, s) is not None
        second = False
        kept = False
        if asked_again:
            login_to_hook(s)
            second = attached_main('C11F')
            _, cap = ssh('warren capture-pane -p -t main', 'C11G')
            kept = mark in cap.splitlines()
        row('C11', written and not prompt and first and seen and asked_again and second and kept,
            f'line written: {written}; a shell prompt at login instead: {prompt}; main with 1 attached: {first}; '
            f'{mark} in main: {seen}; login asked again after the detach: {asked_again}; main with 1 attached '
            f'again: {second}; {mark} kept: {kept}')
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
