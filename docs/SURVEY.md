# Survey: what tmux, zellij and herdr do, and what warren takes

Written from documents and black-box runs only: tmux's manual page and wiki
at 3.4 (the version in the oracle image) with its change log to 3.8; zellij's
user documentation, change log, default configuration, key presets and layout
files at 0.46.0; herdr's documentation and change log at 0.9.5. Every document
is listed with its digest in [SOURCES](SOURCES.md). No source code of any of
the three was read. "Not stated" means the documents read do not say, not
that the program does not do it.

Each section ends with what warren takes. **Decided** marks a decision the
project has already made, with what it costs. **Proposed** marks a
recommendation made by this survey that is not yet decided.

## 1. The session and server model, and where the socket lives

| | tmux 3.4 | zellij 0.46 | herdr 0.9.5 |
|---|---|---|---|
| Model | one server holds every session; clients are separate processes on a socket; the server exits when its last session ends | a background server per session; one socket per session, named by an id, not by the session's name | a background server and any number of clients; each named session is its own server with its own socket |
| Socket | `$TMUX_TMPDIR` or `/tmp`, then `tmux-UID/default`; `-L name`, `-S path` | `$XDG_RUNTIME_DIR/zellij/contract_version_1/`; `ZELLIJ_SOCKET_DIR` overrides | `~/.config/herdr/herdr.sock`, or `sessions/<name>/herdr.sock`; `HERDR_SOCKET_PATH` overrides |
| Permissions | the per-user directory must not be readable, writable or executable by others; anyone who can reach the socket is fully trusted | not stated | not stated for Unix |
| Across versions | not covered | the socket path carries a contract version, so old sessions survive an upgrade | compatible servers keep running; live hand-off is opt-in |

**Decided:** one server per user holding every session, as tmux; clients over
a Unix-domain socket under a per-user runtime directory. The cost is tmux's:
one crash takes every session. What it buys is one place for the command
socket and one process to supervise.

**Proposed:** the socket is `$XDG_RUNTIME_DIR/warren/default` where that
variable is set, else `/tmp/warren-UID/default`, the directory created mode
0700 and refused if it is owned by someone else or is more open than that;
`WARREN_SOCKET` and `-S path` override, `-L name` picks another name in the
same directory. The path socket is the only kind used: PAX has no abstract
socket names. Socket paths are bounded (104 bytes on macOS, 108 on Linux), so
a path that is too long is refused by name before `bind`. The protocol carries
its version in the first message rather than in the path: one server per user
means a version in the path would strand the sessions.

## 2. Attach and detach

| | tmux | zellij | herdr |
|---|---|---|---|
| Attach | `attach [-t s]`, preferring the most recently used unattached session; `new -A` attaches or creates; `-d` detaches the others; `-r` read-only | `attach [name]`, `-c` creates; `watch` is read-only | `herdr` attaches the default session; `session attach name` |
| Detach | prefix `d`; `detach-client` | `Ctrl o d` | prefix `q` |
| The other clients | unaffected | each has its own cursor unless mirrored | each can view its own workspace and tab |
| The terminal dies | the session survives | detaches by default on a hang-up | the server ignores the hang-up and keeps running |

**Decided:** `warren` attaches to the default session or creates it;
`warren new -s NAME`, `warren attach -t NAME`; prefix `d` detaches; several
clients may attach to one session; read-only attach comes later.

**Proposed:** a client that loses its terminal (a hang-up, an end of file, a
write error) is a detach, never an exit of anything else. The server ignores
the hang-up signal and is started in a session of its own, so it outlives the
shell and the login that started it. In v1 all clients of a session see the
same tab and the same focus (mirrored), which is what sizing to the smallest
client assumes; per-client views are a later change that the protocol's
per-client frames already allow.

## 3. Panes, tabs, floating and stacked panes, zoom

| | tmux 3.4 | zellij | herdr |
|---|---|---|---|
| Hierarchy | session, windows, panes | session, tabs, panes | workspace, tabs, panes |
| Split | prefix `"` and `%`; five preset layouts | pane mode `n`, `d`, `r`; swap layouts | prefix `v` and `-` |
| Floating | none (pop-ups only; floating panes arrived in 3.7) | yes, with toggle, embed and pin | not documented |
| Stacked | no | yes | no |
| Zoom | prefix `z` | pane mode `f` | prefix `z` |

**Decided:** session, tabs, and a split tree of panes in each tab; zoom;
floating panes are a second version; layouts are a declarative file from the
first day. The cost of leaving floating panes out is that a pop-up (a picker,
a help screen) has to be drawn by the compositor itself as an overlay rather
than being a pane.

**Proposed:** no stacked panes. A split is binary and carries a ratio, not a
cell count, so a resize of the client is a pure function of the tree and the
new size.

## 4. Keys and modes

| | tmux | zellij | herdr |
|---|---|---|---|
| Prefix | `C-b` | none by default: a key per mode (`Ctrl p` pane, `Ctrl t` tab, `Ctrl n` resize, `Ctrl s` scroll, `Ctrl o` session, `Ctrl g` lock) | `ctrl+b` |
| Modes | key tables: root, prefix, copy-mode, copy-mode-vi, and custom ones | normal, locked, pane, tab, resize, move, scroll, search, three rename modes, session, tmux | terminal, prefix, navigate, copy, resize |
| A way out of key conflicts | rebinding | the "unlock-first" preset: start locked, one key unlocks | direct chords in the `ctrl+alt` family |

What the documents warn about: zellij's per-mode control keys collide with
the programs inside (its first FAQ entry), and a terminal whose Backspace
sends `^H` lands in move mode; herdr's `ctrl+b` takes page-up from programs;
tmux delayed a lone Escape by 500 ms until 3.5 cut it to 10 ms.

**Decided:** modes with an always-visible hint bar, behind a configurable
prefix, Ctrl-Space by default: normal, pane, tab, resize, scroll and copy,
session, command, and a locked mode that passes everything through. After the
prefix: `|` and `-` split, `h j k l` or arrows focus, `H J K L` resize, `c`
new tab, `n` `p` or a digit switch, `z` zoom, `x` close with confirmation, `d`
detach, `[` copy mode, `:` command, `?` the key list. The cost of one prefix
instead of zellij's key per mode is a second keystroke for everything; what
it buys is that exactly one key is taken from the programs inside.

**Proposed:**
- The prefix pressed twice sends the prefix through to the program.
- Ctrl-Space arrives as the byte 0x00 on a terminal without an extended
  keyboard protocol. A terminal that cannot send it (to be measured on PAX's
  console) needs a second default; `Ctrl-a` is the fallback named in the
  configuration reference, not a silent substitution.
- A lone Escape is told from the start of a sequence by a timer of 20 ms,
  configurable; nothing else in the input path waits.
- Mode changes are a table (mode, key, action, next mode) in the
  configuration format, so the hint bar is generated from the same table the
  dispatcher reads and cannot disagree with it.

## 5. The bar and hints

| | tmux | zellij | herdr |
|---|---|---|---|
| Default | one line: session name, window list, pane title, time and date | a tab bar on top and a status bar below; the status bar shows the mode and its keys, and the hints can be clicked | a tab row on top; the status area is empty by default; a sidebar is the main view |
| Without bars | `status off` | hints can move to a corner | configurable |

**Decided:** one line with the session name, the tabs with activity marks,
the mode and the time; a second line of hints unless turned off.

**Proposed:** the bar is drawn by the compositor from session state, never by
a pane or a plugin; both lines are at the bottom; the hint line is the current
mode's row of the key table, truncated on the right with a count of what did
not fit. Clickable hints wait for W4, with the mouse.

## 6. Mouse

| | tmux 3.4 | zellij | herdr |
|---|---|---|---|
| Default | off (on by default from 3.8) | on | on |
| When on | click selects a pane, borders drag, a drag selects and copies on release, right click opens a menu | click, double and triple click select; right click a menu; the wheel scrolls three lines; `Ctrl` with a drag resizes | click focuses, borders drag, a drag selects, double click copies a word, right click a menu |
| A program that asks for reports | events are bindable, and can be forwarded | events go to the program first for click, select and scroll | passed through; a left click still focuses the pane |
| Bypass | Shift (Option in some terminals) gives the outer terminal its own selection | Shift | a configurable modifier for right click |

**Decided:** on by default: a click focuses, borders drag, the wheel scrolls
back, right click opens a pane menu, and events pass through to a program
that has asked for reports; a drag on text selects in copy mode; double click
selects a word. The cost, which all three documents state: with the mouse
captured, the outer terminal's own selection needs Shift.

**Proposed:** a click on an unfocused pane focuses it and is also delivered
to a program there that asked for reports (as herdr; zellij makes this an
option that is off). Coordinates are translated to the pane, and a report is
re-encoded in the encoding the program chose (1006, or the X10 bytes if it
chose none), whatever the outer terminal sent. The wheel over a pane whose
program did not ask for reports scrolls the scrollback; on the alternate
screen with no reports asked, it sends arrow keys (xterm's alternate-scroll
behaviour, mode 1007), three per notch.

## 7. Scrollback and copy

| | tmux | zellij | herdr |
|---|---|---|---|
| Limit | `history-limit`, in lines, for new windows only | 10000 display rows; a wrapped line costs a row per wrap | 10,000,000 bytes per pane |
| Copy mode | prefix `[`; vi or emacs keys; rectangle; search with `/ ? n` | scroll mode; search; edit the scrollback in `$EDITOR`; no keyboard selection bound by default | prefix `[`: `hjkl`, word and paragraph motions, `/ ? n N`, `v` select, `y` copy; output stays live |
| Where the text goes | paste buffers; OSC 52 with `set-clipboard`; an external command | OSC 52 by default; an external command; reads refused | native tools first, OSC 52 as a fallback |

What the documents warn about: allowing OSC 52 reads lets any program in any
pane, even over ssh, read the clipboard; some terminals print OSC 52 as
garbage; xterm ships with it off.

**Decided:** per-pane scrollback under a byte cap; search; a keyboard copy
mode with yew's motions; an internal buffer and OSC 52 outward. A byte cap
(herdr's unit) costs a line count that varies with content; it buys a bound
on memory that a line cap cannot give.

**Proposed:** the cap counts the bytes the scrollback actually holds (its own
encoding, attributes included), default 8 MiB per pane; lines leave from the
oldest end, whole logical lines at a time. OSC 52 is write-only in both
directions: a program inside may set the clipboard only when the
configuration allows it (off by default), and a read request is never
answered. Output stays live while copy mode is open; the view is pinned to
the lines it shows, not to the bottom.

## 8. Configuration and layouts

| | tmux | zellij | herdr |
|---|---|---|---|
| File | a file of tmux commands, read once at server start; `source-file` reloads | KDL, watched and applied live | TOML; a command reloads it; invalid values fall back with a warning |
| Layouts | preset names and layout strings; no layout file | KDL layout files, with swap layouts | none documented; the layout lives in the saved session |

**Decided:** one TOML file, `~/.config/warren/warren.toml`; layouts are a
declarative file from the first day.

**Proposed:** layouts are TOML too, one file per layout, the tree written as
nested tables with a direction, a ratio and, at a leaf, an optional command
and working directory. The configuration is read at server start and on
`warren source FILE` or a reload key; it is not watched. An invalid file
changes nothing and reports every error with its line; a server never starts
half-configured. Client-side settings (colours, the bar) and server-side
settings (shell, scrollback) are told apart in the reference, as herdr does,
because a client of another size or colour depth may attach.

## 9. Scripting and the command line

| | tmux | zellij | herdr |
|---|---|---|---|
| Verbs | a command per operation; targets `session:window.pane` with `$`, `@`, `%` ids | `zellij action VERB`; `run`, `edit`, `pipe`, `subscribe` | a wrapper per noun, each with `--json` |
| Output | format strings; no JSON in 3.4 | `--json` on the list commands; ids are returned | newline-delimited JSON on the socket; a printed schema |
| A program control channel | control mode | plugins | event subscriptions |
| Which pane am I | `TMUX_PANE` | `ZELLIJ_PANE_ID` | `HERDR_PANE_ID` |

**Decided:** a command socket, the same socket the clients use, framed; the
verbs `new`, `attach`, `ls`, `kill-session`, `split`, `send-keys`,
`capture-pane`, `list --json`, `source`, `layout save|load`.

**Proposed:** ids are stable for the life of the server and never reused:
`s1`, `t1`, `p1`. A target is an id, or `session:tab.pane` by name and index.
Every creating verb prints the id it made. `list --json` is the only
machine-readable listing and its schema is versioned in the output. A pane's
environment carries `WARREN` (the socket path) and `WARREN_PANE` (its id), so
a verb run inside a pane defaults to that pane. Exit status: 0 done, 1 the
server refused (with a reason on standard error), 2 usage, 3 no server.

## 10. Persistence

| | tmux | zellij | herdr |
|---|---|---|---|
| Detach | everything lives on | everything lives on | everything lives on |
| The server exits | nothing survives | layout, tabs, panes, working directories and commands are saved every 60 s and restored; commands wait behind a prompt before they run again | workspaces, tabs, panes, working directories, layout and focus come back; processes do not |
| Screen contents | no | opt-in | opt-in, off by default because it may hold secrets |

**Decided:** save the layout and the working directories and restore them;
running programs are not resurrected. The cost is that a restored pane is a
fresh shell in the right place and nothing more.

**Proposed:** saved on every structural change (debounced to one write a
second) and on a clean exit, as one TOML layout file per session under the
state directory, written to a temporary name and renamed. Screen contents and
scrollback are never written to disk in v1. A pane's working directory is
read from the process, where the host can say (`/proc/PID/cwd` on Linux), and
from OSC 7 where the program reports it; where neither exists the pane
restores to the session's starting directory, and the saved file says which
source it used.

## 11. One session, clients of different sizes

- **tmux** has an option with four values: the largest client, the smallest,
  a manual size, or `latest`, the client with the most recent activity, which
  has been the default since 3.1. A window larger than a client is shown in
  part, following the cursor.
- **zellij** (since 0.45) sizes each tab by the clients viewing that tab;
  clients on the same tab converge on a common size, and the documents do not
  say how it is chosen.
- **herdr** follows the client that most recently focused or used the tab,
  and returns to the remaining client's size when the others detach. With no
  client it uses 120 by 40.

**Decided:** sized to the smallest attached client. It costs the larger
client an unused margin; it buys that every client sees the whole of every
pane, and that a resize is caused only by an attach, a detach or a real
resize, never by which client typed last.

**Proposed:** the margin is drawn as a dim filler pattern so that it cannot
be mistaken for pane content. With no client attached a session keeps its
last size; a session created detached is 80 by 24. A client smaller than a
minimum (20 by 6) is attached but not counted, and is shown a message
instead of a frame.

## 12. What the program inside is told

| | tmux | zellij | herdr |
|---|---|---|---|
| `TERM` | `tmux-256color`, `tmux`, `screen-256color` or `screen`, whichever the build found; it must be one of that family | not stated | `xterm-256color`, with `COLORTERM=truecolor` |
| Own variables | `TMUX`, `TMUX_PANE`, `TERM_PROGRAM` | `ZELLIJ`, `ZELLIJ_SESSION_NAME`, `ZELLIJ_PANE_ID` | `TERM_PROGRAM=herdr`, `HERDR_ENV`, ids, the socket path; outer markers of other multiplexers are removed |
| Passthrough | a DCS wrapper, off by default since 3.3 | not stated; a list of forwarded OSC sequences | not documented; titles stop at herdr; OSC 52 writes reach the host |
| Features | a per-terminal feature list for the terminal outside | it asks the outer terminal and advertises only what that supports | Kitty keyboard events forwarded as each program asks |

What the documents warn about: tmux's FAQ opens with "most display problems
are due to incorrect TERM", and a `screen` value loses italics and modified
keys; tmux must be told when the terminal outside has true colour.

**Proposed:** see [TERM](TERM.md) for the measurement and the reasons. In
short: `TERM=xterm-256color`, `COLORTERM=truecolor`, `TERM_PROGRAM=warren`,
on every host; no terminfo entry of warren's own in v1; the emulator's scope
is therefore everything a program can be led to send by that name, which the
prediction lists. No passthrough in v1: a title sets the pane's title, an
OSC 52 write is offered to the clipboard policy, and every other OSC, DCS and
APC string is consumed and dropped whole, never printed. Variables naming
another multiplexer (`TMUX`, `ZELLIJ`, `HERDR_ENV`, `STY`) are removed from a
pane's environment.

## What was not measured

- zellij and herdr were not run. Every statement about them is from their
  documents at the versions named.
- tmux was run only for the rows in `tests/session/`; the rest is its manual.
- Nothing here has been tried on PAX.
