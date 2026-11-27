#!/usr/bin/env python3
"""warren at PAX's console under QEMU: root's shell on the console's own terminal, keys from the emulated keyboard.

    console_rows.py --pax PAX_TREE --warren HOST_WARREN ISO WORK FIRMWARE KEYBOARD [ROWS]

PAX_TREE is a pax checkout; its tools/qemu-run boots ISO (q35, KVM, 2 GiB, the default VGA, so the console draws;
COM1 a socket this script holds; QMP for the monitor's `sendkey`). ISO is an image whose console runs an
interactive root shell with warren, stty, tr, id and tty on PATH. FIRMWARE is bios or uefi. KEYBOARD is usb (an xHCI
USB keyboard, qemu-run's --usb-kbd) or ps2 (the i8042). Command lines are typed through COM1's input, which the
console reads beside the keyboard; every key under test (the prefix, Ctrl-Space, which the console types as NUL,
and the keys after it) is the monitor's `sendkey` on the keyboard. The panes run /bin/sh with a scratch HOME.

The console mirrors what it draws to COM1. The screen is read by replaying those bytes through warren's own
emulator (HOST_WARREN vt-dump at the console's grid, 160x50), so a row reads cells, not a byte stream. COM1 also
carries the kernel's own lines (`user: ...`, between a program's writes), which an image booted `quiet` keeps off
the screen: they are taken out before the replay.

  C0 the console as warren finds it: root, its terminal, TERM, COLUMNS, LINES and the window it reports (printed)
  C1 `warren new -s con`: the session holds at the console's window, or at the documented 80x24 for a 0x0 one:
     `warren list-sessions`, typed inside the pane, shows it attached, from a shell that is not the console's
  C2 Ctrl-Space then |: a vertical border drawn
  C3 a command in the new pane, then Ctrl-Space and h and a command in the first: two shells, neither the console's
  C4 Ctrl-Space and d: `[detached from con]`, exit 0
  C5 `warren attach -t con`: the border and the earlier output drawn again; Ctrl-Space and d detach it again
  C6 `COLUMNS=160 LINES=50 warren new -s big` at a 0x0 window: the session at 160x50; Ctrl-Space and d detach it
  C7 `warren kill-server`: exit 0, and no warren process left (read from /proc)
  C8 (before C7) `warren attach -t con`, then `warren split-down` typed in its pane: exit 0, and a horizontal
     border the screen did not have before it
  C9 (before C7) `warren capture-pane -p -t p2` typed in the same pane: exit 0, and the text holds what the other
     pane printed in C3; then Ctrl-Space and d detach
  C10 (after C7) saved and restored: `warren new -s keep` in one directory, `warren split-right -c` another typed in
     its pane, a detach and `warren kill-server`; then `warren new -d -s probe` says it restored keep, and in
     `warren attach -t keep` each pane's `pwd` is its own directory, the border drawn
ROWS is a comma list (default all). Each row prints PASS or FAIL by name with the firmware and keyboard. The last
line says how the run ended:
  CONSOLE-ROWS FIRMWARE KEYBOARD: PASS (N rows: …)   every asked row passed: exit 0 (exit 1 when no row ran)
  CONSOLE-ROWS FIRMWARE KEYBOARD: FAIL Cn,… (…)      the rows named failed: exit 1
  ROWS-END stopped: WHY   the work directory could not be made; the boot, the console's prompt or the monitor could
                          not be reached; the console closed; or the monitor failed: exit 2. It follows
                          `ROWS-STOPPED why`, which carries what the console last showed; WHY is why up to its first
                          `: `. No CONSOLE-ROWS line is printed, so a reader of that line sees a leg that did not
                          finish.
Run it from a directory of its own: WORK must not exist.
"""
import argparse
import json
import re
import socket
import subprocess
import time
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument('--pax', required=True, type=Path)
ap.add_argument('--warren', required=True, type=Path)
ap.add_argument('iso', type=Path)
ap.add_argument('work', type=Path)
ap.add_argument('firmware', choices=['bios', 'uefi'])
ap.add_argument('keyboard', choices=['usb', 'ps2'])
ap.add_argument('rows', nargs='?', default='C0,C1,C2,C3,C4,C5,C6,C7,C8,C9,C10')
args = ap.parse_args()
ROWS = args.rows.split(',')
FW, KBD = args.firmware, args.keyboard
COLS, LINES = 160, 50
WORK = args.work.resolve()
try:
    WORK.mkdir(parents=True, exist_ok=False)
except OSError as e:
    print(f'ROWS-STOPPED the work directory could not be made: {e}', flush=True)
    print('ROWS-END stopped: the work directory could not be made', flush=True)
    raise SystemExit(2)
raw = WORK / f'console-{FW}-{KBD}.serial'
raw.write_bytes(b'')
bad, asked = [], []
buf = bytearray()


def row(name, ok, what):
    asked.append(name)
    print(f'{"PASS" if ok else "FAIL"} {name} {FW} {KBD}: {what}', flush=True)
    if not ok:
        bad.append(name)


KERNEL_LINE = re.compile(rb'user: [^\r\n]*\r?\n')


def drawn(since=0):
    """COM1's bytes from `since` without the kernel's own lines: what the console drew."""
    return KERNEL_LINE.sub(b'', bytes(buf[since:]))


def screen():
    """The console's screen now: COM1's bytes so far replayed through warren's emulator, as lines of text."""
    path = WORK / 'replay.bin'
    path.write_bytes(drawn())
    out = subprocess.run([str(args.warren), 'vt-dump', '--cols', str(COLS), '--rows', str(LINES), str(path)],
                         capture_output=True, timeout=60).stdout.decode('utf-8', 'replace')
    lines = [[' '] * COLS for _ in range(LINES)]
    r = 0
    for line in out.splitlines():
        if line.startswith('row '):
            r = int(line.split()[1])
            continue
        m = re.match(r'^(\d+)(?:-(\d+))? (\d) (\S+)', line)
        if not m or r < 1:
            continue
        a, b, width, chars = int(m[1]), int(m[2] or m[1]), m[3], m[4]
        if width == '0' or chars == '-':
            continue
        ch = ''.join(chr(int(p, 16)) for p in chars.replace('U+', ' ').split('+') if p.strip())
        for c in range(a, b + 1):
            lines[r - 1][c - 1] = ch
    return [''.join(x).rstrip() for x in lines]


def shown(pattern, lines=None):
    for line in lines if lines is not None else screen():
        m = re.search(pattern, line)
        if m:
            return m
    return None


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


def stream_text(since=0):
    plain = re.sub(rb'\x1b\[[0-9;?<>= ]*[A-Za-z]|\x1b[()][A-Za-z0-9]|\x1b[=>78]|\x1b\][^\x07]*\x07', b'', drawn(since))
    return plain.replace(b'\r', b'').decode('utf-8', 'replace')


def until_stream(pattern, timeout, since):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pump(0.3)
        m = re.search(pattern, stream_text(since), re.M)
        if m:
            return m
        if q.poll() is not None:
            return None
    return None


def until_screen(pattern, timeout):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        pump(0.5)
        m = shown(pattern)
        if m:
            return m
        if q.poll() is not None:
            return None
    return shown(pattern)


def typed(b):
    """A command line through COM1's input, 20 ms a byte."""
    for ch in b:
        try:
            c.sendall(bytes([ch]))
        except OSError as e:
            raise SystemExit(f'the console closed: {e}') from None
        time.sleep(0.02)
        pump(0)


class Mon:
    def __init__(self, path):
        t0 = time.monotonic()
        while not path.exists() and time.monotonic() - t0 < 30:
            time.sleep(0.1)
        self.s = socket.socket(socket.AF_UNIX)
        self.s.settimeout(30)
        try:
            self.s.connect(str(path))
            self.r = self.s.makefile('rb')
            json.loads(self.r.readline())
        except (OSError, ValueError) as e:
            raise SystemExit(f'the monitor could not be reached: {e}') from None
        self.cmd('qmp_capabilities')

    def cmd(self, name, arguments=None):
        p = {'execute': name}
        if arguments is not None:
            p['arguments'] = arguments
        try:
            self.s.sendall(json.dumps(p).encode() + b'\n')
            while True:
                reply = json.loads(self.r.readline())
                if 'return' in reply or 'error' in reply:
                    return reply
        except () as e:
            raise SystemExit(f'the monitor failed: {e}') from None

    def sendkey(self, keys):
        """The monitor's own `sendkey KEYS` on the emulated keyboard."""
        r = self.cmd('human-monitor-command', {'command-line': f'sendkey {keys}'})
        if 'error' in r or r.get('return'):
            print(f'NOTE sendkey {keys}: {r}', flush=True)
        time.sleep(0.15)
        pump(0)


def prefix_then(key):
    mon.sendkey('ctrl-spc')
    pump(0.3)
    mon.sendkey(key)


def border_on(lines):
    return any('│' in line for line in lines)


def across(lines):
    """The rows that hold a horizontal border: a run of at least 20 of U+2500."""
    return {i for i, line in enumerate(lines) if '─' * 20 in line}


com = WORK / 'com1.sock'
qmp_path = WORK / 'qmp.sock'
argv = [str(args.pax / 'tools/qemu-run'), '--firmware', FW, '--accel', 'kvm', '--timeout', '1500',
        '--serial-chardev', f'socket,path={com},server=on,wait=on']
if KBD == 'usb':
    argv += ['--usb-kbd']
argv += [str(args.iso.resolve()), '--', '-m', '2048M', '-qmp', f'unix:{qmp_path},server=on,wait=off']
print('qemu-run: ' + ' '.join(argv), flush=True)
q = subprocess.Popen(argv, cwd=args.pax, stdin=subprocess.DEVNULL, stdout=open(WORK / f'console-{FW}-{KBD}.qemu', 'wb'),
                     stderr=subprocess.STDOUT)
c = None
mon = None
stopped = ''
try:
    t0 = time.monotonic()
    while not com.exists() and time.monotonic() - t0 < 30:
        time.sleep(0.1)
    c = socket.socket(socket.AF_UNIX)
    try:
        c.connect(str(com))
    except OSError as e:
        raise SystemExit(f'the console could not be reached: {e}') from None
    up = until_stream(r'[$#] $', 300, 0)
    print(f'the console\'s prompt: {up is not None} after {time.monotonic() - t0:.0f} s; '
          + next((line for line in stream_text().splitlines() if line.startswith('kernel: ')), '(no kernel line)'), flush=True)
    if up is None:
        raise SystemExit('no prompt: ' + stream_text()[-600:])
    mon = Mon(qmp_path)
    s = len(buf)
    typed(b'export SHELL=/bin/sh HOME=/tmp/wh; mkdir -p $HOME; cd $HOME; '
          b'echo C0 uid=$(id -u) tty=$(tty) term=$TERM cols=[$COLUMNS] lines=[$LINES] size=[$(stty size)] pid=$$ C0-END\r')
    c0 = until_stream(r'^C0 uid=(\S+) tty=(\S+) term=(\S*) cols=\[(.*)\] lines=\[(.*)\] size=\[(.*)\] pid=(\d+) C0-END$', 20, s)
    console_pid = c0[7] if c0 else '?'
    if c0:
        print(f'MEASURE console uid={c0[1]} tty={c0[2]} TERM={c0[3]} COLUMNS=[{c0[4]}] LINES=[{c0[5]}] stty-size=[{c0[6]}]',
              flush=True)
    if 'C0' in ROWS:
        row('C0', c0 is not None and c0[1] == '0', f'the console: {c0[0] if c0 else repr(stream_text(s)[-200:])}')
    size = '80x24'
    if c0 and re.fullmatch(r'\d+ \d+', c0[6]) and c0[6] != '0 0':
        rr, cc = c0[6].split()
        size = f'{cc}x{rr}'
    typed(b'warren new -s con\r')
    pump(3)
    typed(b'warren list-sessions; echo C1-pid=$$\r')
    listed = until_screen(r'con: (\d+x\d+) \((\d+) attached\)', 20)
    pane = until_screen(r'C1-pid=(\d+)', 10)
    if 'C1' in ROWS:
        ok = listed is not None and listed[1] == size and listed[2] == '1' and pane is not None and pane[1] != console_pid
        row('C1', ok, f'warren new -s con: listed {listed[0] if listed else "nothing"} (want {size}, 1 attached) from '
            f'pane shell {pane[1] if pane else "?"} (console shell {console_pid})'
            + ('' if ok else '; screen: ' + ' | '.join(line for line in screen() if line)[-400:]))
    prefix_then('shift-backslash')
    pump(2)
    border = until_screen('│', 10) is not None
    if 'C2' in ROWS:
        row('C2', border, f'Ctrl-Space then |: a border drawn: {border}')
    typed(b'echo C3-$$-R\r')
    right = until_screen(r'C3-(\d+)-R', 15)
    prefix_then('h')
    pump(1)
    typed(b'echo C3-$$-L\r')
    left = until_screen(r'C3-(\d+)-L', 15)
    if 'C3' in ROWS:
        ok = right is not None and left is not None and right[1] != left[1] and console_pid not in (right[1], left[1])
        row('C3', ok, f'the new pane\'s shell {right[1] if right else "?"}, after Ctrl-Space and h the first pane\'s '
            f'{left[1] if left else "?"} (console shell {console_pid})')
    s5 = len(buf)
    prefix_then('d')
    det = until_stream(r'\[detached from con\]', 20, s5)
    until_stream(r'[$#] $', 10, s5)
    s6 = len(buf)
    typed(b'echo C4-st=$?\r')
    st = until_stream(r'^C4-st=(\d+)$', 10, s6)
    if 'C4' in ROWS:
        row('C4', det is not None and st is not None and st[1] == '0',
            f'Ctrl-Space and d: {det[0] if det else repr(stream_text(s5)[-160:])}; exit {st[1] if st else "?"}')
    until_stream(r'[$#] $', 10, s6)
    s7 = len(buf)
    typed(b'warren attach -t con\r')
    again = until_screen(r'C3-\d+-[RL]', 15)
    lines = screen()
    redrawn = again is not None and border_on(lines)
    prefix_then('d')
    det2 = until_stream(r'\[detached from con\]', 20, s7)
    if 'C5' in ROWS:
        row('C5', redrawn and det2 is not None, f'warren attach -t con: the border and the earlier output drawn again: '
            f'{redrawn}; detached again: {det2 is not None}')
    until_stream(r'[$#] $', 10, s7)
    s8 = len(buf)
    typed(b'COLUMNS=160 LINES=50 warren new -s big\r')
    pump(3)
    typed(b'warren list-sessions\r')
    big = until_screen(r'big: (\d+x\d+) \((\d+) attached\)', 20)
    prefix_then('d')
    det3 = until_stream(r'\[detached from big\]', 20, s8)
    if 'C6' in ROWS:
        want = size if size != '80x24' else '160x50'
        row('C6', big is not None and big[1] == want and det3 is not None,
            f'COLUMNS=160 LINES=50 warren new -s big: listed {big[0] if big else "nothing"} (want {want}); '
            f'detached: {det3 is not None}')
    until_stream(r'[$#] $', 10, s8)
    s81 = len(buf)
    typed(b'warren attach -t con\r')
    until_screen(r'C3-\d+-[RL]', 15)
    pump(1)
    before = across(screen())
    typed(b'warren split-down; echo C8-st=$?-END\r')
    st8 = until_screen(r'C8-st=(\d+)-END', 20)
    pump(2)
    added = across(screen()) - before
    if 'C8' in ROWS:
        row('C8', st8 is not None and st8[1] == '0' and len(added) > 0,
            f'warren split-down typed in a pane: exit {st8[1] if st8 else "?"}; new horizontal border rows '
            f'{sorted(added) or "none"}' + ('' if added else '; screen: ' + ' | '.join(line for line in screen() if line)[-400:]))
    typed(b'c=$(warren capture-pane -p -t p2); s=$?; case "$c" in *C3-*-R*) r=has ;; *) r=not ;; esac; '
          b'echo C9-st=$s-$r-END\r')
    st9 = until_screen(r'C9-st=(\d+)-(has|not)-END', 20)
    if 'C9' in ROWS:
        row('C9', st9 is not None and st9[1] == '0' and st9[2] == 'has',
            f'warren capture-pane -p -t p2 typed in a pane: exit {st9[1] if st9 else "?"}; the other pane\'s C3 line '
            f'{"held" if st9 and st9[2] == "has" else "not held"}')
    prefix_then('d')
    until_stream(r'\[detached from con\]', 20, s81)
    until_stream(r'[$#] $', 10, s81)
    s9 = len(buf)
    typed(b'warren kill-server; echo C7-k=$?\r')
    kk = until_stream(r'^C7-k=(\d+)$', 20, s9)
    until_stream(r'[$#] $', 10, s9)
    pump(3)
    s10 = len(buf)
    typed(b'for d in /proc/[0-9]*; do c=$(tr "\\000" " " < $d/cmdline 2>/dev/null); case $c in *warren*) '
          b'echo "left ${d#/proc/} $c" ;; esac; done; echo C7-scanned\r')
    sc = until_stream(r'^C7-scanned$', 60, s10)
    left_over = [line for line in stream_text(s10).splitlines() if line.startswith('left ') and '*warren*' not in line]
    if 'C7' in ROWS:
        row('C7', kk is not None and kk[1] == '0' and sc is not None and not left_over,
            f'kill-server exit {kk[1] if kk else "?"}; warren processes left: {left_over or "none"}')
    until_stream(r'[$#] $', 10, s10)
    s11 = len(buf)
    typed(b'mkdir -p /tmp/wh/c10a /tmp/wh/c10b; cd /tmp/wh/c10a; warren new -s keep\r')
    pump(3)
    typed(b'warren split-right -c /tmp/wh/c10b; echo C10-split=$?-END\r')
    split10 = until_screen(r'C10-split=(\d+)-END', 15)
    pump(2)
    prefix_then('d')
    until_stream(r'\[detached from keep\]', 20, s11)
    until_stream(r'[$#] $', 10, s11)
    s12 = len(buf)
    typed(b'warren kill-server; warren new -d -s probe; echo C10-new=$?\r')
    newst = until_stream(r'^C10-new=(\d+)$', 40, s12)
    notice = re.search(r'warren: restored (\d+) saved sessions?: ([^\n]*)', stream_text(s12))
    until_stream(r'[$#] $', 10, s12)
    s13 = len(buf)
    typed(b'warren attach -t keep\r')
    pump(3)
    typed(b'echo C10-L=$(pwd)-END\r')
    left10 = until_screen(r'C10-L=(/\S*)-END', 15)
    prefix_then('l')
    pump(1)
    typed(b'echo C10-R=$(pwd)-END\r')
    right10 = until_screen(r'C10-R=(/\S*)-END', 15)
    bordered = border_on(screen())
    prefix_then('d')
    until_stream(r'\[detached from keep\]', 20, s13)
    until_stream(r'[$#] $', 10, s13)
    if 'C10' in ROWS:
        ok = (split10 is not None and split10[1] == '0' and newst is not None and newst[1] == '0' and notice is not None
              and 'keep' in notice[2].split(', ') and left10 is not None and left10[1] == '/tmp/wh/c10a'
              and right10 is not None and right10[1] == '/tmp/wh/c10b' and bordered)
        row('C10', ok, f'saved and restored: split {split10[1] if split10 else "?"}; new -d {newst[1] if newst else "?"}; '
            f'{notice[0] if notice else "no restore notice"}; left pane {left10[1] if left10 else "?"}, right pane '
            f'{right10[1] if right10 else "?"}, border {bordered}'
            + ('' if ok else '; screen: ' + ' | '.join(line for line in screen() if line)[-400:]))
    typed(b'warren kill-server\r')
    pump(2)
    print('NOTE the console\'s last lines: ' + ' | '.join(stream_text().strip().splitlines()[-4:]), flush=True)
except SystemExit as e:
    stopped = str(e) or 'stopped'
    print(f'ROWS-STOPPED {stopped}', flush=True)
finally:
    if c is not None:
        c.close()
    if q.poll() is None:
        q.terminate()
        try:
            q.wait(timeout=20)
        except subprocess.TimeoutExpired:
            q.kill()
            q.wait()
if stopped:
    print(f'ROWS-END stopped: {stopped.splitlines()[0].split(": ", 1)[0]}', flush=True)
    raise SystemExit(2)
print(f'CONSOLE-ROWS {FW} {KBD}: ' + ('FAIL ' + ','.join(bad) if bad else 'PASS') + f' ({len(asked)} rows: {",".join(asked)})',
      flush=True)
raise SystemExit(1 if bad or not asked else 0)
