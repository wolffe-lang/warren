# The command line: verbs, targets, ids, exit statuses

`warren VERB [-t TARGET] [-c DIR] [ARGUMENT...] [-- CMD [ARG...]]` sends one command to the server over
the same socket clients attach through, prints the server's answer (standard
output and standard error), and exits with the answer's status.

## Exit statuses

| status | meaning |
|---|---|
| 0 | done |
| 1 | the server refused the verb; the reason is on standard error |
| 2 | a usage error: an unknown verb, a missing or extra argument |
| 3 | no server answered (`warren: no server is running`) |

## Verbs

The server's own verbs take no target:

| verb | what it does |
|---|---|
| `kill-server` | stops the server; every attached client is told |
| `list-sessions`, `ls` | one line a session: `NAME: COLSxROWS (N attached)` |
| `new-session [-c DIR] [-l LAYOUT] [NAME]` | makes a session (named by the lowest free number when no name is given) and prints its name; its first pane's program starts in DIR; with `-l` its tabs, panes, focus, zoom and active tab are the layout file's (LAYOUT.md), and DIR is its start directory |
| `list --json` | the server's sessions, tabs and panes as one JSON object (below) |

Two verbs act on a pane but are not command line verbs (they print, or type
for a program): `send-keys` and `capture-pane`, each below. They take
`-t TARGET` among their own options.

Every verb of the command line (`:` in a client) is also a verb here, read by
the same parser, so a verb and its `:` line always mean the same action:
`split-right`, `split-down`, `focus-next`, `zoom`, `equalize`, `close-pane`,
`new-tab`, `close-tab`, `next-tab`, `previous-tab`, `focus DIRECTION`,
`resize DIRECTION [N]`, `select-tab N`, `rename-tab NAME`, `kill-session`,
`rename-session NAME`, `detach`, `lock`, `source [FILE]`, `layout save NAME`
and `layout load NAME`. A command line verb takes `-t TARGET` anywhere after
the verb, at most once, except `source`, which takes none.

- `kill-session` ends the target's session: every pane's program hangs up and
  every client attached to it is told the session ended. Ending the last
  session ends the server, as the last pane's end does.
- `rename-session NAME` renames the target's session; a name the server does
  not allow (empty, holding `/` or a control byte) or one another session
  holds is refused, status 1.
- `detach` sent from a shell detaches every client attached to the target's
  session; the session lives on. At the `:` line it detaches only the client
  that typed it.
- `source [FILE]` reads `warren.toml` again, or FILE (relative to the
  directory `warren` runs in), and applies its settings at once; a refused
  file changes none and is named by line, status 1 (CONFIG.md).
- `lock` acts on the client that typed it, so sent from a shell it is refused:
  `warren: lock: acts on an attached client`.
- `layout save NAME` writes the target's session as a layout file and prints
  its path; `layout load NAME` opens a layout file's tabs after the target
  session's and prints each new tab's id, one a line. NAME is a file in the
  layouts directory (`~/.config/warren/layouts/NAME.toml`), or a word holding
  `/` a file path, relative to the directory `warren` runs in. A refused load
  changes nothing and names the file and line: `warren: layout load: dev line
  6: no such directory: /srv/gone`, status 1. LAYOUT.md has the file and every
  rule.

## Making panes: `-c DIR` and `-- CMD`

`split-right`, `split-down` and `new-tab` take `-c DIR`, the directory the new
pane's program starts in. Without it, a split starts in the working directory
of the pane it splits (its `cwd` in `list --json`), and a new tab in the
session's start directory. The verbs also take
`-- CMD [ARG...]`, the program it runs (else the configured shell); every word
after `--` is the program's, `-t` and `-c` among them. `new-session` takes
`-c DIR` alone. A relative DIR is read from the directory `warren` was run in.
Each of these verbs prints the id of the pane it made (`p7`) and a newline;
`new-session` prints its name.

CMD runs as the words given, with no shell in between: `warren split-right --
vim 'my notes.txt'` gives vim one argument, and `$HOME` in a word stays
`$HOME`. A shell is asked for by name: `warren split-right -- sh -c 'make;
read x'`.

A DIR that is not a directory (`no such directory: DIR`) and a program found
neither at its path nor on the session's `PATH` (`the program did not start:
...`) are refused, status 1, before anything is made: the panes, the focus and
the tabs stay as they were. A program that starts and exits at once ends its
pane as a shell that exits does. `-c` and `--` belong to a shell's words: the
`:` line, which has no shell quoting, does not take them.

A command line verb acts on its target's pane as a key would on the focused
pane, and then leaves the session's focus and its active tab where they were,
except for the verbs whose purpose is to move them: `focus`, `focus-next`,
`zoom`, `select-tab`, `next-tab` and `previous-tab`. So `warren split-right
-t work` splits `work`'s focused pane and keeps that pane focused, where tmux
would focus the new one.

Other differences from tmux, on purpose: a creating verb always prints the id
it made (tmux prints it only with `-P`), and `-- CMD` runs the words given as
the program's arguments where tmux runs a command through `sh -c`.

`warren --version`, with no other argument, prints `warren` and the package
version on one line and exits 0, before any verb is looked up and without a
server. The version is the one `src/wolf.pkg` names; with any other argument
`--version` is a usage error, status 2.

## `send-keys [-t TARGET] [-l] [--] KEY...`

Types into the target pane's program, past the key table: no prefix, no
binding, whatever mode a client is in. Options come only before the first
key, and `--` ends them, so `warren send-keys -t p2 ls -l Enter` types `ls`,
`-l` and Enter.

- A word is a key when it is one of tmux's names, in any case: `Up`, `Down`,
  `Left`, `Right`, `Home`, `End`, `PPage`/`PageUp`/`PgUp`,
  `NPage`/`PageDown`/`PgDn`, `IC`/`Insert`, `DC`/`Delete`, `BSpace`, `Tab`,
  `BTab`, `Enter`, `Escape`, `Space`, `F1` to `F12`, `KP0` to `KP9`, `KP.`,
  `KP/`, `KP*`, `KP-`, `KP+`, `KPEnter`; or one character. Modifiers come
  first: `C-` or `^` (Ctrl), `M-` (Alt), `S-` (Shift, only before the keys
  whose sequences carry it: the cursor keys, Home, End, the page keys,
  Insert, Delete, F1 to F12). Any other word (`Esc`, `F13`, `S-a`, `ls -l`) is
  text, typed a character at a time; `-l` makes every word text.
- Each key is sent as the key would type it in the pane's mode (application
  cursor keys and keypad included), by the path a client's keys take. tmux
  3.4 was measured key by key (`tests/session/send-keys.table`): every
  name agrees but for three, named there and here. Home and End go as xterm
  types them (`ESC [ H`, `ESC [ F`; `ESC O H`, `ESC O F` in application
  cursor mode), where tmux sends `ESC [ 1 ~`, `ESC [ 4 ~`. Keypad Enter
  outside keypad mode is CR, where tmux sends LF. Ctrl with a key that has no
  control byte (C-1, C-3 to C-8, C-0, C-BSpace, C-Enter, C-Escape) is the key
  as typed (the digit, BS, CR, ESC), where tmux sends nothing.
- A send is all or nothing: its bytes fit the pane's 64 KiB input queue, or
  it is refused (status 1) and none are sent. No key at all is a usage error
  (status 2), where tmux succeeds and sends nothing. tmux's `-H`, `-K`, `-M`,
  `-N`, `-R`, `-X`, `-F` and `-c` are refused by name.

## `capture-pane [-t TARGET] [-p] [-e] [-J] [-S LINE] [-E LINE]`

The target pane's rows as text, one line a row with a newline after each.
With `-p` it is printed; without, it goes to the session's register, as
tmux's goes to a paste buffer, and the paste key (prefix `]`) types it.

- Lines: 0 is the first visible row, -1 history's newest row. `-S` defaults
  to 0 and `-S -` is history's first row; `-E` defaults to, and `-E -` is,
  the last visible row. `+N` is N. A line outside clamps to the nearest, and
  an end before the start is swapped, as tmux does. A value that is not a
  line is a usage error (status 2), where tmux takes it as the default. On the
  alternate screen there is no history, where tmux's negative lines still
  reach the main screen's.
- A row's trailing blanks are dropped. With `-e`, a space written in a
  rendition other than the default stays, and each change of rendition is
  written as the whole pen from a reset (`ESC [ 0;… m`), with a reset at a
  line's end; tmux writes each change as it comes, so the bytes differ while
  the cells are the same. With `-J`, rows are joined at a soft wrap and a
  row's written trailing spaces stay; a column a wide character could not use
  does not.
- Flags may be clustered (`-pJ`). A printed capture past the protocol's
  8 MiB, or a kept one past the register's 65,524 bytes, is refused by name
  (status 1). tmux's `-a`, `-A`, `-b`, `-C`, `-N`, `-P`, `-q` and `-T` are
  refused by name.

## Saved sessions

Every live session is saved, so that a server that starts again makes it
again. A session's file is `$XDG_STATE_HOME/warren/sessions/NAME.toml`, or
`~/.local/state/warren/sessions/NAME.toml`; the directories are made at
0700 and the file is 0600. It is the session as `layout save` writes it, with
one more table, `[session]`: its name, start directory and size (LAYOUT.md,
Layout files). Screen contents and scrollback are never written.

- **When.** A session is written when its text changes, at most once a
  second, so its file is at most a second behind; and every live session is
  written when the server stops (`kill-server`, TERM or INT) before any
  pane's program hangs up. Each write goes to a temporary name, is synced,
  then renamed, so a file is whole or not there.
- **What removes a file.** Ending the session: `kill-session`, or its last
  pane's exit. A rename moves the file to the new name. A `kill-server`, a
  stop by signal and a crash keep every file.
- **Restore.** A server that starts makes every saved session again before
  its socket is bound, in file-name order, each under its own name at its
  saved size. Every pane starts the configured shell in its saved directory;
  a pane's saved command is not run again, and the next save writes none for
  it. Ids are new. After a crash every saved session comes back.
- **What warren prints.** The client that started the server prints what was
  restored, once, on standard error, before it attaches or runs its verb:

  ```
  warren: restored 2 saved sessions: notes, work
  warren: not restored: mail: mail line 16: no such directory: /home/me/gone (kept: /home/me/.local/state/warren/sessions/mail.toml; remove it to discard it)
  ```

  A client that reaches a running server prints nothing. The same lines, each
  after the time in milliseconds, go to `restore.log` beside `sessions` (the
  newest 100 lines), with the first failed write of each session.
- **Discarding one.** `warren kill-session -t NAME` ends a restored session and
  removes its file. A file that cannot be made is kept as it is and tried at
  every start; remove it to discard the session, or put back what it needs
  (its directory, say) to have it made. Removing `NAME.toml` before a start
  discards it too.
- **Turning it off.** `restore = false` in `warren.toml` (CONFIG.md) saves
  nothing and restores nothing; it is the only switch, and files already
  written stay.

## Targets

```
TARGET  = ID | SESSION [ ":" TAB [ "." PANE ] ]
ID      = "s" N | "t" N | "p" N | "%" N
```

- An id is read first. `sN` is a session (its active tab's focused pane),
  `tN` a tab (its focused pane), `pN` a pane; `%N` is a pane too, the form
  `WARREN_PANE` carries. N is written without a leading zero.
- Otherwise the whole text names a session by its exact name. A session's
  name is never an index: sessions are named `1`, `2` and so on by default.
- Otherwise the text is parted at its last `:` into a session's name and a
  tab. The tab is a 1-based index when it is digits alone, else a tab's name.
  A last `.` in the tab parts off a pane only when digits follow it: the
  pane's 1-based index in the tab's tree order (a split's first side before
  its second).
- With no `-t`, a verb run inside a pane acts on that pane (the client sends
  its `WARREN_PANE`). Outside any pane, with exactly one session, it acts on
  that session's focused pane.

A target that leads nowhere is refused, status 1, by one of these names:
`no-such-session`, `no-such-tab`, `no-such-pane`, `malformed` (an empty
session, tab or pane part), `ambiguous` (no target, no pane to run in, and
more than one session). Nothing changes.

## Ids

Sessions, tabs and panes each have an id from a counter of their own that
never goes back: a closed pane's, an ended session's or a closed tab's id is
never handed out again while the server runs. Ids are spelled `s1`, `t1`,
`p1`, in one place in the source (`src/cmd/ids.lu`).

## `list --json`, schema 2

One line, the object below, then a newline. Field order is fixed, so two
listings of one state are equal byte for byte.

```json
{"schema":2,"sessions":[
  {"id":"s1","name":"work","cols":80,"rows":24,"clients":1,"active_tab":"t1","tabs":[
    {"id":"t1","name":"","index":1,"focus":"p2","zoomed":false,"panes":[
      {"id":"p1","index":1,"col":1,"row":1,"cols":40,"rows":22,"pid":4201,"title":"sh",
       "cwd":"/home/me/src","cwd_source":"osc7"},
      {"id":"p2","index":2,"col":42,"row":1,"cols":39,"rows":22,"pid":4202,"title":"",
       "cwd":"/home/me","cwd_source":"proc"}]}]}]}
```

Schema 2 adds two fields to each pane, after `title`: `cwd` and
`cwd_source`. Every field of schema 1 is unchanged, in name, meaning and
order.

- `sessions` in id order; `tabs` in their order (`index` from 1); `panes` in
  the tab's tree order (`index` from 1, the index a target names).
- `cols` and `rows` of a session are its size; `clients` the clients attached.
- A pane's `col` and `row` (from 1) and `cols` and `rows` place it inside the
  tab area, which is the session's size less the bar's two lines. A pane a
  zoomed tab hides has the zero rect: `0, 0, 0, 0`.
- `pid` is the pid of the pane's program, or `null` when it has ended.
- `cwd` is the pane's working directory, and `cwd_source` where it was learnt.
  `osc7` means the directory the pane's program last reported with OSC 7
  ([TERM](TERM.md)). `proc` means the directory `/proc` names for its program,
  on Linux, while the program runs. `start` means the directory its program
  started in (`-c DIR`, a layout file leaf's `cwd`, or the directory of the
  pane it was split from), or its session's start directory once that one is
  gone, used when neither of the others is available. A reported or read
  path is used only while it names a directory that exists, so a shell whose
  directory was removed is listed at `start`. On macOS and PAX there is no
  `proc`.
- Strings are written as they are in UTF-8, with a quote and a backslash
  escaped and every byte below 0x20, and 0x7f, as `\u00XX`.
- A tab's `name` is empty until it is renamed.
