# The terminal client

`warren` with no arguments attaches the terminal it runs in to the default
session, starting the server (detached, in a session of its own, its standard
streams on `/dev/null`) and the session when there are none. `warren attach
[-t NAME]` attaches to a session that exists and is refused when it does not.
`warren new [-d] [-s NAME]` makes a session and attaches to it. `warren
kill-server` and `warren list-sessions` ask a running server over the command
role. Later verbs (`detach`, `split`, `tab`, ...) fail by name.

## Sessions and clients

`warren new` makes a session at this terminal's size, in this directory and
with this environment, prints its name and attaches to it. With `-d` it makes
the session and returns (at 80x24 when there is no terminal, or at `COLUMNS` by
`LINES` when both are set: see "The window's size" below). Without `-s` the
server names it with the lowest positive number not in use. A name in use is
refused, and so are an empty name and one holding `/` or a control byte; names
are compared as bytes.

Several clients may attach to one session. The pane takes the smallest
columns and, separately, the smallest rows of the clients attached. When a
client detaches, ends or loses its terminal, the pane and the other clients go
on, and the size follows the clients left. With nobody attached the session
keeps its last size.

The server runs in a session of its own, detached from the terminal of the
client that started it: that client can end, or its terminal go away, and the
server and its sessions stay for the next `warren attach`. The server stops on
`kill-server`, or a while after its last session has ended with no client
connected. On PAX the server outlives the client that started it; surviving a
logout of the console waits on PAX keeping its first process (pax#358) and is
not promised here.

A command the server does not know is refused with the usage status and its
name, so a newer client facing an older server fails cleanly.

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
complete kitty functional-key support. A bare ESC still waits the same 30 ms.


What the terminal sends becomes protocol events: Unicode scalars and C0
controls as keys (Ctrl-Space is the prefix), cursor, editing and function keys
with xterm's modifier parameter, keypad keys in application mode, SGR and
legacy mouse reports, bracketed paste (at most 64 KiB a PASTE; a longer paste goes as
several) and focus reports. A lone ESC waits 30 ms for the rest of a sequence
before it is the Escape key; an unfinished sequence at that point, or one
longer than 64 bytes, goes to the pane unchanged. The server's own encoding of
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
on exit, so programs inside can receive hover when they ask for it. Wheel
scrollback controls remain planned.

## Rendering

The client keeps what the terminal shows and sends only the cells that change,
placing the cursor after each wide glyph explicitly: widths come from the
server's images, never from a Unicode table. The policy comes from the
environment:

| policy | when | colours | wide glyphs | marks | sync, cursor shape |
|---|---|---|---|---|---|
| terminal | default | RGB with `COLORTERM=truecolor` or `24bit`; 256 with `TERM` naming `256color`; else 16; none for `TERM=dumb` | the glyph, then the next cell placed | sent | yes |
| console | `WARREN_RENDER=console` (PAX's console) | 16 | the glyph, then a blank for its continuation | left out, later cells keep their columns | no |

Colours a policy cannot show are downsampled: RGB to the nearest of the 6x6x6
cube or the grey ramp, and either to the nearest of the sixteen. The console
policy sends only CSI sequences: no OSC, DCS or APC. Rows render images into
warren's own emulator as the outer terminal and compare every cell, at every
depth, for full repaints and deltas over a seeded soak; a model of a
one-cell-a-code-point console holds the console policy.

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
takes about 0.8 ms on Linux and a one-cell delta about 0.08 ms
(`MEASURE render` in the compose rows).
