# What warren tells the programs inside

A program in a pane learns what terminal it is on from `TERM`, sometimes
from `COLORTERM`, and, on hosts that have one, from the terminfo entry that
`TERM` names. This file records what the hosts have, what the organisation's
own programs look at, and what warren should therefore say.

## What was measured

**The other multiplexers.** tmux tells its panes `TERM=tmux-256color`
(measured, tmux 3.4 in the oracle image: `tests/session`, row
`tmux-pane-environment`), and its manual requires a value from the `screen`
or `tmux` family, each of which needs its terminfo entry on every host the
user reaches; its FAQ opens with the trouble that causes. herdr tells its
panes `TERM=xterm-256color` and `COLORTERM=truecolor`. zellij's documents do
not say.

**PAX has no terminfo database.** Its console session exports `TERM=linux`;
a session over ssh carries whatever the client sent. Nothing on the image
reads a terminfo entry.

**The organisation's programs decide from the names alone.**

| Program | What it reads | What follows |
|---|---|---|
| yew | `COLORTERM`, then patterns in `TERM`; it also asks the terminal (device attributes, a mode report) | 24-bit colour when `COLORTERM` says so; 256 when `TERM` contains `256color`; 16 for `TERM=linux`; no attributes for `dumb` |
| pelt | `TERM`, `COLORTERM` | the line editor is off for `dumb`; 16 colours for `linux`; 24-bit when `COLORTERM` is `truecolor`; 256 for `256color` |
| quarry | `TERM`, `NO_COLOR` | ASCII borders for an empty or `dumb` `TERM` |

None of them consults terminfo, on any host.

**What `xterm-256color` promises.** On hosts with terminfo, a program that
uses it sends what the entry lists. The entry was read with `infocmp -x -1`
in the oracle image (ncurses 6.4.20240113, run as a binary; the output's
digest is in [SOURCES](SOURCES.md)). Its output side is: cursor addressing
and relative moves, tabs and back-tab, erase in line and display (and
scrollback, `E3`), insert and delete of characters and lines, `ech`, `rep`,
scroll up and down (`indn`, `rin`), the scroll region, index and reverse
index, save and restore cursor, SGR including italic, dim, strike, invisible
and the 256-colour forms, the DEC graphics set (`smacs`/`rmacs`), insert
mode, autowrap on and off, cursor keys and keypad modes (`smkx`), the
alternate screen with a title-stack push and pop, cursor shape (`Ss`, `Se`),
bracketed paste, focus events, SGR mouse, OSC 52 (`Ms`), cursor and palette
colours (OSC 4, 12, 104, 112), a visible bell made of reverse video, soft
reset, full reset, left and right margins, a meta-key mode, printing, and
the device-attribute and version queries.

## Recommendation

**`TERM=xterm-256color`, `COLORTERM=truecolor`, `TERM_PROGRAM=warren` and
`TERM_PROGRAM_VERSION`, on every host, PAX included. No terminfo entry of
warren's own in the first version.**

Why:

- It is the one name that is present wherever terminfo is, so a pane that
  runs ssh to another machine keeps working. An entry of warren's own would
  have to be installed on every host a user reaches; that is the trouble
  tmux's FAQ describes.
- On PAX the name is only ever compared as a string, and this string sends
  yew, pelt and quarry down their best paths. `TERM=linux` inside a pane
  would hold them to 16 colours although the pane's grid keeps every colour.
- What the outer terminal can draw is the client's concern, not the
  program's. On PAX's console the client reduces colours to the console's
  sixteen and places every character itself; the program inside does not
  need to know.

What it costs:

- **The name is a promise.** Everything in the list above can arrive. The
  first emulator serves all of it that changes the screen, and consumes the
  rest whole without effect. The prediction lists each sequence under one or
  the other. The ones consumed without effect are: left and right margins,
  the title stack, the reverse-video bell, palette and cursor colour changes,
  the meta-key mode, printing.
- **Two answers differ from xterm's on purpose.** The device-attribute
  answers describe warren, not xterm (no sixel, no ReGIS), and the version
  query names warren. A program that tells terminals apart by those answers
  will see a terminal it does not know and should fall back to what the
  entry says.
- **Keys must match the entry too.** The entry's key capabilities are what
  curses programs expect to read, so the server's key encoder produces
  xterm's sequences in each cursor-key and keypad mode.
- **`xterm-256color` says nothing of what warren has beyond it**
  (synchronized output, underline styles). Programs that probe, as yew does,
  find them; programs that only read terminfo do not. An entry of warren's
  own that adds them is a later, optional step, and can be offered beside
  this default without changing it.

The alternatives, for the record:

| | For | Against |
|---|---|---|
| `tmux-256color` | truthful about being a multiplexer; programs with tmux-specific paths use them | absent from the system terminfo of some hosts; promises tmux's passthrough and behaviours warren does not have |
| an entry of warren's own | exact | must be installed everywhere; nothing reads it on PAX |
| `linux` on PAX | matches the console | holds every program to 16 colours and the console's key forms, for no gain: the pane is not the console |

## Identity and query bytes

The pure emulator answers these queries, with `ESC` = byte 1B and no spaces
between the bytes shown in backticks:

| Query | Exact answer |
|---|---|
| `ESC [ c`, `ESC [ 0 c`, or `ESC Z` | `ESC [ ? 6 2 ; 2 2 c` |
| `ESC [ > c` or `ESC [ > 0 c` | `ESC [ > 0 ; 1 ; 0 c` |
| `ESC [ > q` or `ESC [ > 0 q` | `ESC P > \| w a r r e n SPACE VERSION ESC \` |

DA1 uses the VT220-style form and advertises only ANSI colour (feature 22).
It claims no printer, ReGIS, sixel, selective erase, downloadable keys or
other optional feature. A feature number may be added only with its
implementation and a row proving it. DA2 uses VT100 family 0, warren's small
firmware/protocol revision 1, and cartridge 0; programs keying behaviour on
a DA2 version number will deliberately see a small one, not xterm's patch
number. `VERSION` is generated at build preparation from the sole version
field in `src/wolf.pkg`; it is not a second hand-maintained literal and is
not read from the filesystem at runtime. A row compares the real answer
byte-for-byte with that manifest, and a changed-manifest fixture proves
that build preparation regenerates it.

Other identity parameter values, unknown/private variants (apart from the
specified `>` queries), and DA3 get no answer. Status reports are
`ESC [ 0 n` for DSR 5, `ESC [ row ; col R` for DSR 6, and
`ESC [ ? row ; col R` for DEC DSR 6. Rows are relative to the scroll-region
top while origin mode is set. DECRQM uses the documented `CSI mode;status$y`
form, with `?` preserved for DEC queries. Unsupported modes report 0;
fixed-on/off supported modes report 3/4.

The queue is exactly 4096 bytes. If one complete answer cannot fit, that
query is dropped whole, without disturbing earlier answers or preventing a
later smaller answer from fitting. Draining clears it. Query input never
allocates answer storage; a row fills 4092 bytes, drops an oversized CPR,
then admits a four-byte status answer exactly at the cap.

## Also set and unset

`WARREN` (the socket's path) and `WARREN_PANE` (the pane's id) are set.
`TMUX`, `TMUX_PANE`, `STY`, `ZELLIJ`, `ZELLIJ_SESSION_NAME`, `ZELLIJ_PANE_ID`
and `HERDR_ENV` are removed, so a program does not address another
multiplexer's protocol to warren. `LINES` and `COLUMNS` are removed: the
pane's size is the pty's.
