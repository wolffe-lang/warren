# The configuration file

warren reads one file, `warren.toml`, when its server starts:
`$XDG_CONFIG_HOME/warren/warren.toml` when `XDG_CONFIG_HOME` is set and not
empty, otherwise `~/.config/warren/warren.toml`. With no file every setting
has its default. A running server keeps the settings it started with; stop it
(`warren kill-server`) and start it again to read the file again.

The file is a strict subset of TOML. A line is blank, a comment (`#` to the end
of the line, also after a value), a table header such as `[clipboard]`, or
`key = value` inside a table. Spaces around names and `=` do not matter. Values
are the bare words `true` and `false`. Anything else refuses the whole file: an
unknown table or key, a key outside a table, a value of another kind, a table
or key given twice, or a header without its `]`. A refused file changes no
setting, and every client that attaches is told why on its hint line, for
example `warren.toml line 3: unknown table [keys]`. A file that cannot be read
is refused the same way.

## `[clipboard]`

| key | values | default | what it does |
|---|---|---|---|
| `programs` | `true`, `false` | `false` | Whether a program in a pane may write the clipboard of your terminal through warren with OSC 52. |

warren's own copies (a mouse selection's release) always go to the terminal of
the client that made them, as an OSC 52 write, when that terminal takes them
(CLIENT.md). A program inside a pane can ask for the same thing with its own
OSC 52 sequence. By default warren keeps such writes to itself, so a program,
or a remote host behind ssh, cannot set your clipboard. With `programs = true`
the write is passed to every client of the session whose terminal takes OSC 52
writes. Reads of the clipboard are never answered, whatever this setting says.

```toml
# Let programs in panes set my terminal's clipboard.
[clipboard]
programs = true
```
