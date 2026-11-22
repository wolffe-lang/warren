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
| `new-session [-c DIR] [NAME]` | makes a session (named by the lowest free number when no name is given) and prints its name; its first pane's program starts in DIR |
| `list --json` | the server's sessions, tabs and panes as one JSON object (below) |

Every verb of the command line (`:` in a client) is also a verb here, read by
the same parser, so a verb and its `:` line always mean the same action:
`split-right`, `split-down`, `focus-next`, `zoom`, `equalize`, `close-pane`,
`new-tab`, `close-tab`, `next-tab`, `previous-tab`, `focus DIRECTION`,
`resize DIRECTION [N]`, `select-tab N`, `rename-tab NAME`, `kill-session`,
`rename-session NAME`, `detach` and `lock`. A command line verb takes
`-t TARGET` anywhere after the verb, at most once.

- `kill-session` ends the target's session: every pane's program hangs up and
  every client attached to it is told the session ended. Ending the last
  session ends the server, as the last pane's end does.
- `rename-session NAME` renames the target's session; a name the server does
  not allow (empty, holding `/` or a control byte) or one another session
  holds is refused, status 1.
- `detach` sent from a shell detaches every client attached to the target's
  session; the session lives on. At the `:` line it detaches only the client
  that typed it.
- `lock` acts on the client that typed it, so sent from a shell it is refused:
  `warren: lock: acts on an attached client`.

## Making panes: `-c DIR` and `-- CMD`

`split-right`, `split-down` and `new-tab` take `-c DIR`, the directory the new
pane's program starts in (else the session's start directory), and
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

## `list --json`, schema 1

One line, the object below, then a newline. Field order is fixed, so two
listings of one state are equal byte for byte.

```json
{"schema":1,"sessions":[
  {"id":"s1","name":"work","cols":80,"rows":24,"clients":1,"active_tab":"t1","tabs":[
    {"id":"t1","name":"","index":1,"focus":"p2","zoomed":false,"panes":[
      {"id":"p1","index":1,"col":1,"row":1,"cols":40,"rows":22,"pid":4201,"title":"sh"},
      {"id":"p2","index":2,"col":42,"row":1,"cols":39,"rows":22,"pid":4202,"title":""}]}]}]}
```

- `sessions` in id order; `tabs` in their order (`index` from 1); `panes` in
  the tab's tree order (`index` from 1, the index a target names).
- `cols` and `rows` of a session are its size; `clients` the clients attached.
- A pane's `col` and `row` (from 1) and `cols` and `rows` place it inside the
  tab area, which is the session's size less the bar's two lines. A pane a
  zoomed tab hides has the zero rect: `0, 0, 0, 0`.
- `pid` is the pid of the pane's program, or `null` when it has ended.
- Strings are written as they are in UTF-8, with a quote and a backslash
  escaped and every byte below 0x20, and 0x7f, as `\u00XX`.
- A tab's `name` is empty until it is renamed. A pane's working directory is
  not in schema 1.
