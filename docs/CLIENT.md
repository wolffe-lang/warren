# The terminal client

`warren` with no arguments attaches the terminal it runs in to the default
session, starting the server (detached, in a session of its own, its standard
streams on `/dev/null`) and the session when there are none. `warren attach
[-t NAME]` attaches to a session that exists and is refused when it does not.
`warren new [-A] [-d] [-s NAME] [-l LAYOUT]` makes a session and attaches to it. `warren
kill-server` and `warren list-sessions` ask a running server over the command
role. Later verbs (`detach`, `split`, `tab`, ...) fail by name.

## Sessions and clients

`warren new` makes a session at this terminal's size, in this directory and
with this environment, prints its name and attaches to it. With `-d` it makes
the session and returns (at 80x24 when there is no terminal, or at `COLUMNS` by
`LINES` when both are set: see "The window's size" below). Without `-s` the
server names it with the lowest positive number not in use. A name in use is
refused, and so are an empty name and one holding `/` or a control byte; names
are compared as bytes. With `-l LAYOUT` the session is a layout file's: its
tabs, panes, focus, zoom and active tab (`new-session -l`, LAYOUT.md); a
relative path is read from this directory. With `-A` and `-s NAME`, a session
NAME that exists is attached (or, with `-d`, its name printed) and nothing is
made, as tmux's `new-session -A` does: `-l` is not applied to it, and two
`new -A -s NAME` at once make one session. `-A` without `-s` is refused.

Several clients may attach to one session. The pane takes the smallest
columns and, separately, the smallest rows of the clients attached. When a
client detaches, ends or loses its terminal, the pane and the other clients go
on, and the size follows the clients left. With nobody attached the session
keeps its last size.

The server runs in a session of its own, detached from the terminal of the
client that started it: that client can end, or its terminal go away, and the
server and its sessions stay for the next `warren attach`. The server stops on
`kill-server`, or a while after its last session has ended with no client
connected. On PAX the server outlives the client that started it, and on an
installed PAX it outlives the console's logout too: a session made at the
console is there, with its panes' output, after `exit` and a new login, and no
restore was needed to make it (the console row L1, `tests/pax/login_rows.py`,
on an installed PAX image under QEMU).

A command the server does not know is refused with the usage status and its
name, so a newer client facing an older server fails cleanly.

## Starting at login

PAX's `/etc/shrc` runs the account's own file, `$HOME/.config/pelt/shrc`, last,
when it is a readable regular file. This one line there starts warren at login:

```
[ -z "$WARREN" ] && [ -t 0 ] && exec warren new -A -s main
```

- At a console login the shell is replaced by a client attached to the
  session `main`, made when there is none (`new -A`, above).
- A pane's environment has `WARREN` (TERM.md), so a shell in a pane does not
  start a second client. `[ -t 0 ]` passes over a shell with no terminal.
- Because of `exec`, a detach ends the login. On an installed PAX the system
  then asks `login:` again. The server and `main` go on, and the next login
  attaches to the same `main`, with its panes and their output.
- A terminal over ssh runs the same file, and its client reaches the same
  server as the console's (SERVER.md, the runtime directory;
  `tests/pax/burrow_rows.py`), so it attaches to the same `main`. No row runs
  the line over ssh yet.
- A command over ssh (`ssh HOST COMMAND`) runs no `/etc/shrc`, so the line
  never reaches it. That makes it a way to take the line out without a
  terminal: `ssh HOST 'mv ~/.config/pelt/shrc ~/.config/pelt/shrc.off'`.
- On PAX's dev and release images the console's shell is the first process,
  and `exec` would replace it. The line is for an installed system.

The console row C11 (`tests/pax/login_rows.py`, the file's path an argument)
measures the console half on an installed PAX image under QEMU:
- the line is written and the console logs out;
- the next login attaches to `main`;
- a detach from ssh brings `login:` back;
- the login after that attaches to the same `main`, its output kept.

## The window's size

The client makes and attaches a session at the window its terminal reports
(`TIOCGWINSZ`). A terminal that reports a dimension as 0 has not been told its
size: a serial line, or a console that draws a grid it does not report (PAX's
console under QEMU reports 0x0 while it draws 160x50). For such a dimension the
client takes `COLUMNS` (or `LINES`) from its environment when it is a positive
number no larger than 65,535, and otherwise 80 columns (or 24 rows); a
dimension the terminal reports is kept, whatever the environment says. So
`warren` at a 0x0 window attaches at 80x24, and `COLUMNS=160 LINES=50 warren`
at 160x50. When the window later changes, a dimension it reports as 0 keeps its
last size.

A window the protocol cannot carry (more than 65,535 in a dimension, or more
than 262,144 cells) is refused by name before the client starts a server or
takes the terminal: `warren: the terminal's window 600x500 is larger than
warren takes (262144 cells)`. A smaller window than 20x6 is the server's to
refuse (too small, below).

## The terminal, taken and given back

Before anything changes, the client reads the terminal's mode and registers
its restore with the runtime, with the bytes that leave what the client turns
on. Then it sets the terminal raw (every byte as typed, both ways, and no
signal keys: Ctrl-C, Ctrl-Z and Ctrl-\ reach the pane as bytes) and enters the
alternate screen, bracketed paste, focus reports and SGR mouse reports.

Every way the client ends gives the terminal back: its mode as it was and the
leave bytes written (mouse, focus and bracketed paste off, the pen reset, the
cursor shown at its default shape, the alternate screen left). The client
rows hold this for each way out:

| how it ends | exit code | line on standard error |
|---|---:|---|
| detached (the prefix Ctrl-Space then `d`) | 0 | `[detached from NAME]` |
| the session ended | 0 | `[NAME ended]` |
| the server stopped | 0 | `[the server stopped]` |
| too small (a resize below 20x6) | 1 | `warren: the terminal is too small (...)` |
| refused (no such session, limits) | 1 | `warren: refused: ...` |
| the server closed without a BYE | 1 | `warren: the server closed the connection` |
| a HELLO the client's codec refuses (a bug) | 1 | `warren: the hello could not be sent: ...` |
| an image that does not apply | 1 | `warren: the server sent an image that does not apply` |
| terminate, hangup, quit or interrupt signals | 1 | `warren: ended by a signal` |
| the terminal closed or cannot be written | 1 | `warren: the terminal closed` / `cannot be written` |
| standard input is not a terminal | 1 | `warren: not a terminal: ...` (nothing was changed) |
| a window larger than warren takes | 1 | `warren: the terminal's window CxR is larger than ...` (nothing was changed) |

A suspend (`SIGTSTP` sent to the client) gives the terminal back first, then
stops; on continue the client takes it again and asks for a full repaint.
`SIGKILL` runs no code: the terminal stays raw, and the rows report that
rather than promise otherwise (`stty sane` or `reset` restores it).

## Input

The Alt quick keys arrive as an ESC prefix in legacy input. The parser also
accepts CSI-u scalar key reports: press and repeat act once, releases do not
act, and a supplied shifted alternative or associated text is retained.
ASCII letters and the Shift+backslash quick key have a fallback when no
shifted value is supplied. Caps/Num Lock do not create extra shortcut
modifiers. Super/Hyper/Meta chords, unsupported functional key presses and malformed
reports remain raw input rather than being mistaken for an Alt shortcut.
Modifier-only reports for representable modifiers are consumed. This does
not enable or negotiate a new terminal keyboard mode, and is not a claim of
complete kitty functional-key support. A bare ESC is the Escape key at once
(below).


What the terminal sends becomes protocol events: Unicode scalars and C0
controls as keys (Ctrl-Space is the prefix), cursor, editing and function keys
with xterm's modifier parameter, keypad keys in application mode, SGR and
legacy mouse reports, bracketed paste (at most 64 KiB a PASTE; a longer paste goes as
several) and focus reports. A read that ends in ESC is the Escape key at once
(ESC ESC, Escape with Alt): a terminal writes a key's sequence whole, so
nothing behind it is coming, and the program behind the pane, which may wait
for its own escape timeout, is not kept waiting for the client's too. Only a
sequence that a read cut after `ESC [`, `ESC O` or inside a scalar waits
30 ms for the rest; an unfinished sequence at that point, or one longer than
64 bytes, goes to the pane unchanged. So the events do not depend on where the
reads split the input, except right after a leading ESC, as in any terminal:
there a split reads as the Escape key and then the rest. The server's own encoding of
every named key and modifier parses back to the same event (a row). What a key
does (the prefix, the modes, the prompts) is the server's key table, per client
(SERVER.md §8); the client sends every key as it is.

Mouse coordinates are outer-frame cells. Clicking a pane focuses it; that
first gesture does not reach its program. Later clicks in the focused pane
reach programs that requested mouse reports, in their chosen encoding.
Clicking a tab label switches tabs using the spans of the image this client
acknowledged, even if output has since changed live activity marks or another
client renamed a label. A removed tab's stale label consumes the gesture,
rather than selecting a different tab that shifted into its place. Even a
pixel-identical replacement publishes an ACKable zero-cell image so the new
identity becomes clickable. A plain border click is inert; dragging moves that
split with minimum-size clamps, even when the pointer leaves its original pane
area. The terminal client requests all-motion reporting (1003) and disables it
on exit, so programs inside can receive hover when they ask for it. The wheel
goes to the focused pane's program when it asked for reports; otherwise, over
a pane on its primary screen, it opens this client's scroll mode there
(SERVER.md §8). On the alternate screen without reports it does nothing. A
left drag in such a pane (or a Shift drag in one that asked for reports)
selects text for this client; release copies it into the session's register.
A drag whose pane ends before its release copies nothing, even when a new pane
has taken that pane's place.

The client tells the server (HELLO feature bit 3) that its terminal takes OSC
52 clipboard writes, except under the console policy (below), which never
gets one. For each CLIPBOARD the server sends, it writes
`ESC ] 52 ; c ; base64 BEL` to the terminal: best effort, write-only, never
read back, so a terminal may refuse or ignore it and the register still holds
the text. The server sends CLIPBOARD for this client's own copies; a program's
own OSC 52 write in a pane reaches the terminal only when `warren.toml` allows
it ([CONFIG](CONFIG.md)).

## Rendering

The client keeps what the terminal shows and sends only the cells that change,
placing the cursor after each wide glyph explicitly: widths come from the
server's images, never from a Unicode table. The policy comes from the
environment:

| policy | when | colours | wide glyphs | marks | sync, cursor shape |
|---|---|---|---|---|---|
| terminal | default | RGB with `COLORTERM=truecolor` or `24bit`; 256 with `TERM` naming `256color`; else 16; none for `TERM=dumb` | the glyph, then the next cell placed | sent | yes |
| console | `TERM=linux` with `WARREN_RENDER` unset (PAX's console, a Linux virtual console), or `WARREN_RENDER=console` | 16 | the glyph, then a blank for its continuation | left out, later cells keep their columns | no |

`WARREN_RENDER`, when set, decides either way: `console` picks the console
policy under any `TERM`, and any other value (`terminal`, say) picks the
terminal policy even under `TERM=linux`. Since a Linux virtual console says
`TERM=linux` as PAX's console does, the console policy is its default too
(sixteen colours, wide glyphs placed for one cell a code point, no OSC);
`WARREN_RENDER=terminal` keeps the terminal policy there.

Colours a policy cannot show are downsampled: RGB to the nearest of the 6x6x6
cube or the grey ramp, and either to the nearest of the sixteen. The console
policy sends only CSI sequences: no OSC, DCS or APC. A delta is drawn from the
runs it applied: when the terminal shows the image the delta was applied to,
only those runs are compared, drawn where they changed, and copied into what
the client keeps of the terminal; a full image, a new size or a screen the
client no longer knows compares every cell. Each pen's escape is built once a
render. Rows render images into
warren's own emulator as the outer terminal and compare every cell, at every
depth, for full repaints and deltas over a seeded soak; a model of a
one-cell-a-code-point console holds the console policy
(`src/client_spans_test.lu` holds a delta to its runs).

## Memory

The client's memory does not grow with the frames it draws. It keeps one image
of what the terminal shows, refilled in place after a full image and changed in
place by the runs each delta applied (at 160x50 an image is 448,000 bytes). Each turn of its loop, one wait and what
it reported, runs in a region that is freed when the turn ends: the messages
read, the bytes drawn and sent, and the events typed go with it. What outlives
the turns is changed in place: the connection's received bytes and the texts
its messages carried (the title, the session's name, the reason it ended), the
image, the input parser's pending bytes and paste, and the window last sent.
The compiler holds the loop to this, since a call inside the turn's region may
not keep anything of the region in what it was handed. A client row on Linux
(where /proc gives the resident set) holds it: see Measured.

## Measured

The client rows run natively on Linux and macOS, and on PAX under QEMU from a
console transcript, with the client in a pseudo-terminal of the rows' own.
They hold every way out above and the sessions-and-clients rules: `new`
detached, numbered, refused and attached; a second client at a smaller size
beside the first, then gone; the server outliving the client that started it;
a verb the server does not know; the names a session may hold; and a
terminal whose window is 0x0 (attached at 80x24, or at `COLUMNS` by `LINES`) or
larger than warren takes (refused before anything starts). At PAX's own
console under QEMU, `tests/pax/console_rows.py` holds the same session as root
on the console's terminal, with keys from the emulated keyboard (MAP). On Linux,
the first prompt after starting the server is drawn about 0.1 s after the
client starts, and `new -d` against a running server takes about 40 ms from
its start to its exit.
Attached to one 80x24 session, the client's resident size peaks at 4-5.2 MB
on Linux and 10.3 MB on PAX (`MEASURE client`). Rendering a full 80x24 image
takes about 0.8 ms on Linux; a one-cell delta, which reads only its run, takes
about 5 µs at 80x24 and 7 µs at 320x90 (`MEASURE render` in the compose rows).
On Linux, where /proc gives the resident set, the `memory-bounded` row holds a
client at 160x50 drawing a pane that scrolls without pause: over 400 renders
past a 50-render warm-up its resident set grows by no more than 4 MiB
(`MEASURE client-rss`, read every 25 renders; the row stops at the first
reading past the bound).
