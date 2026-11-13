# Sources

warren is written in a clean room. This file records every document actually
consulted, with a digest where the document is a file, and what it was used
for. The lists of what may and may not be read are in the README. The
reference programs were run as binaries and never opened as implementations.

## Consulted for grammar and character editing (2026-11-13 UTC)

**ECMA-48, fifth edition, June 1991**, fetched from
https://ecma-international.org/wp-content/uploads/ECMA-48_5th_edition_june_1991.pdf,
SHA-256 `9577ad2514c411584b274ef7a4b3238c80aa93defbb349b18b8c78f78873f450`
(checked twice). Clauses 5.4, 5.4.1 and 5.4.2 specify CSI byte ranges,
private parameters, decimal substrings and omitted defaults; 5.6 specifies
control-string delimiters. The definitions checked directly are 8.3.6 CAN,
8.3.16 CSI, 8.3.26 DCH, 8.3.38 ECH and 8.3.64 ICH. The editing definitions
put opened/vacated positions into the erased state and discard shifted
contents at the boundary. Terminal-profile behavior, including the ICH
cursor position and application-specific cancellation, follows the pinned
control-sequences document and measured cases rather than claiming every
ECMA device mode is implemented. No implementation source was consulted.

## Consulted for DEC graphics and saved cursors (2026-11-13 UTC)

The DEC **VT100 User Guide**, chapter 3, at
https://vt100.net/docs/vt100-ug/chapter3.html, SHA-256
`f2264dfbfc0277b7a59764284336ab509011ce229f322dd0d2a61724d914c7b2`
(checked twice): table 3-9 names the 32 special graphics; the DECSC prose
specifies saved position, graphic rendition and character set; DECALN
specifies uppercase E screen alignment. These are documentation, not an
emulator implementation. The patch-390 control-sequences document also
specifies the 1047/1048/1049 transitions and REP's preceding-graphic form.
The committed `ris` census summary shows the window title surviving reset;
the adopted draft now states that boundary explicitly.

## Consulted for query answers (2026-11-13 UTC)

The exact patch-390 control-sequences document listed below was fetched
again from the same digest-matching binary package, extracting only the
manual. Its decompressed SHA-256 matched
`18117bddcde059b8e371722ee3e5998be2404c0614017ea30a8a1b7b1d912de6`.
The DA1 optional-feature list, DA2 fields, DSR 5/6, DECRQM/DECRPM and
XTVERSION clauses define the response forms. Warren's identity values are
fixed in [TERM](TERM.md), not copied from xterm's responses. The pinned
compiler's build help was checked for metadata injection options; the build
instead prepares an ignored version member from the single manifest field.

## Consulted for width generation (2026-11-13 UTC)

- Unicode 15.1.0 `UnicodeData.txt`, `EastAsianWidth.txt`,
  `DerivedCoreProperties.txt` and `emoji-data.txt`, fetched as normative data
  from unicode.org. Exact URLs and SHA-256 pins are in
  `tests/vt/unicode-sources.json`; each local input digest was checked twice.
  The generator uses Mn/Me, default-ignorable Cf, W/F and Emoji_Presentation,
  with zero width taking precedence, then applies the five stated exception
  classes in `tests/vt/width-exceptions.json`. It imports no code from input folders.
- Unicode's 15.1 ReadMe identifies the final 2023-08-28 data;
  SHA-256 `0d2da782ead4e85630d510f50808355e8c3355e670841d257dd1e6fbd40db9fa`.
  Unicode License V3 is included as `LICENSE-UNICODE`, SHA-256
  `e7a93b009565cfce55919a381437ac4db883e9da2126fa28b91d12732bc53d96`.
- The pinned image's public libc `wcwidth`/`iswprint` ABI, called as a black
  box in `C.UTF-8`: glibc 2.39 accepts the 15.1 sample U+2FFC but rejects the
  16.0 sample U+1C89. This identity probe supports the pin; it is not the
  complete assigned-scalar sweep. The replacement-table development sweep
  measured all 287346 assigned scalars: 65 controls and zero non-control
  differences. The 350 explicit width exceptions agree with black-box glibc
  `wcwidth` and reference CPR. Actual warren input, `wcswidth` and reference
  CPR all measure the US/GB indicator pairs as two cells. No libc source was
  opened. The earlier 350-difference result remains historical evidence only.
- Twenty-eight two-pass zero-width cell captures measure seven representative
  scalars after ASCII, after a wide base, on an unwritten addressed cell and
  at the first column. Jamo and U+13430 are printed attached to existing bases;
  U+FFF9 is omitted in all four contexts. Twelve full-cell prints retain a
  mark on an unwritten cell while the ordinary print reports zero extent;
  the strict validator still rejects those inconsistent reports. Raw bytes,
  checksums and both print passes are in `tests/vt/reference/zero-width`.
- wolf-std commit `77cf3210a82c93dc05ded987c249bb69e79b0a89`, documented
  `std.str` header (through line 210) and `std.fmt` header (through line 45):
  no display-width family exists at this pin; padding counts bytes, not terminal
  columns. Full-file SHA-256 identities checked twice are respectively
  `76cf9a66c029cbc092641da0db805d988ddb1293fc322bfe387ad1fea5fac856` and
  `16062a3401432140a005bd055a01fea3319e612c29cc585824a1435ea1c3cdb3`.
  Only those documented boundaries were consulted for the std comparison;
  no absent function or substitute width measurement is invented.
- The pinned wolf language specification's memory-model and types documents
  and public region conformance examples, for retained arena charges and
  affine region ownership. The replacement-storage witness does not infer
  per-buffer reclamation from list replacement; the adopted draft instead
  budgets peak capacities and retained growth buffers explicitly. The scalar
  Cell copy path also follows `[mem.tier0.move.3]` and the documented container
  index-store rule: scalar-only structs copy independently without region
  allocation. `src/vt/copy_rows.lu` checks that value/alias and allocation
  contract on native and lupin rather than assuming it from native speed.

## Consulted for the incremental parser (2026-11-12)

- The adopted emulator contract in `notes/wr00-draft-wr01-emulator.md`, its
  scope table in `notes/wr00-the-map.md`, and the census byte streams.
- The pinned reference emulator, run only as a binary for nineteen additional
  synthetic edge streams. `tests/vt/parser-reference/manifest.json` binds each
  input and whole-screen snapshot to SHA-256 and the existing emulator and
  package pins. The package list and all four oracle binary digests matched.
- The pinned wolf-std modules' documented interfaces for lists, raw bytes,
  region accounting, file I/O, hex encoding and the monotonic clock. Clock
  reads occur only in the measurement entry, never inside `src/vt`.
- The pinned lupin binary's CLI help and release README for its observation
  interface. No evaluation-step count is exposed for a successful run; the
  measurement therefore reports a bytes-per-step lower bound from its fixed
  50,000,000-step ceiling, not an invented exact count.

The primary terminal documents already listed below have not been fetched
again for this parser-only slice. Their clause check and the Unicode width
sweep remain part of the screen-model work.

## Consulted for the scaffold (2026-11-12)

| Reference | Identity | Use |
|---|---|---|
| wolf release v0.2.39 | release metadata read twice (`tests/pin-read-1.json`, `-2.json`); archive digests in `wolf-toolchain.toml` | the compiler pin |
| lupin release v0.1.61 | the same | the reference interpreter pin |
| wolf-std commit `77cf3210a82c93dc05ded987c249bb69e79b0a89` | tree `8ed51cc10bbe18b2fc7734c802af84422873899f` | the standard library pin; its `std.term`, `std.process`, `std.signal` and `std.net.unix` documentation for the calls the server will use |
| Organisation code: sniff's and burrow's `ci/` and `tools/` | their trunks | the shape of the tier planner, the gate, the toolchain fetcher and the snapshot-pinned image |

## Consulted for the oracle and the emulator's draft (2026-11-12)

| Reference | Identity | Use |
|---|---|---|
| **XTerm Control Sequences** (`ctlseqs.txt`), "updated for XTerm Patch #390 (2024/02/19)" | `/usr/share/doc/xterm/ctlseqs.txt.gz` of Ubuntu's `xterm_390-1ubuntu3_amd64.deb` (sha256 `3541b6956d6c4be71db7b66ec91985bd5eb128fb130e806f1c879f9d94a97c72`); the file's sha256 `8020de0f161d2a8311b468f646eb41b4fb3f25b582eb118e075d2841ef3c7cff`, decompressed `18117bddcde059b8e371722ee3e5998be2404c0614017ea30a8a1b7b1d912de6`, 3,575 lines | the document of record: it is the reference emulator's own, at the reference's own version. Section names in the prediction are its headings. The queries the harness uses (CPR, DECCIR, DECTABSR, DECRQSS, DECRQM, DECRQCRA, DECCRA, media copy, window reports) |
| the same document at patch 411 | cited by PAX's `docs/SOURCES.md` | not read in this lane; W1 reads it for what changed after 390 |
| **xterm(1)**, the manual page | `/usr/share/man/man1/xterm.1.gz` of the same package; sha256 `15b00c6a980100f7cd5ed903801c1e6f4db86d52df67f1e426be0ea139426dc6`, decompressed `6e1009c939e43df0c0d7a7a1289e4d9fe09ab3ce8d46060c641608102e2ae0d9` | the resources the harness sets: `printerCommand`, `printAttributes`, `printerExtent`, `printerAutoClose`, `checksumExtension`, `precompose`, `allowWindowOps`, `decTerminalID`, `utf8` |
| ECMA-48, fifth edition | fetched in W1; PDF digest and checked clauses above | control grammar, cancellation and editing definitions; it was not fetched during the scaffold slice |
| terminfo entries `xterm-256color`, `tmux-256color`, `linux` | the output of `infocmp -x -1` (ncurses 6.4.20240113, binary sha256 in `warren-oracle.toml`) in the oracle image; sha256 `3d3199307af19c9896cc368406ac5eaae134f7b93bb61566aeb854eae964298a`, `866b5efc77151c33470bd14faaafb20799eecaffbbb6de709f4474d25046975d`, `6f168924ab419936011b7f8577ba55a5128ee79b9a1108fd888b896cbbede3ab` | what a program is led to send by each name (`docs/TERM.md`) |
| Organisation code: PAX's console and screen, its pseudo-terminal notes, yew's terminal layer, pelt's line editor, quarry, burrow's session code | their trunks | what the console serves; what the organisation's programs send and read |

The package's `xterm.terminfo` file was not opened: the entries were read
through `infocmp`, a binary, so that nothing from a terminal emulator's or
ncurses's source tree was read.

### Binary observations, not sources

| Program | Identity | Observed |
|---|---|---|
| xterm 390 | binary sha256 in `warren-oracle.toml` | every dump under `tests/vt/` and `tests/corpus/` |
| tmux 3.4 | the same | `tests/session` rows: a pane's environment, text and cursor of six cases, the size of a session shared by two clients |
| yew, pelt, den, quarry | built from their public trunks at the commits below, with their own pinned toolchains | the recordings in `tests/corpus/` |

| Recorded program | Commit |
|---|---|
| yew | `727b6056c2c87aa5b2e891eeb58edbcc9a6cccda` |
| pelt | `b80d6570a4611d7977e4cf489c192849b32a6a7f` |
| den | `f344f0042c3125c6ffb1cdf53251c7a17ed80949` |
| quarry | `a4db62f9b7e80bce4d7e8c8927b27ef2d8af1dd0` (built with this repository's pinned toolchain) |

## Consulted for the survey (fetched 2026-11-12)

Documents only: manuals, wikis, change logs, READMEs, user documentation,
default configuration, key presets and layout files. Each was fetched with
an undisguised client and is listed with its digest. zellij's default
configuration, key presets and layouts are data files in its repository;
they were read as the documents its manual points to. One registry refused
automated clients and was not asked again.

### tmux (manual and CHANGES at 3.4; CHANGES at 3.8; the wiki)

| Document | Source | Bytes | SHA-256 |
|---|---|---|---|
| tmux-3.4.1 | https://raw.githubusercontent.com/tmux/tmux/3.4/tmux.1 | 173761 | `cbae510c504a1147c2d0fbdf4cd4bbb10eabdc64f14162b83151f3480c780df7` |
| CHANGES-3.4 | https://raw.githubusercontent.com/tmux/tmux/3.4/CHANGES | 143346 | `3cb7e0362e825b7d72fdfc9b21fbeac718b5eaf268822cf6450f76fc5694f065` |
| wiki-Getting-Started.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Getting-Started.md | 54997 | `7f8ca65017b2c19796de0392d19b414dd1d56899171204a08bed6a6a749f48a3` |
| wiki-Clipboard.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Clipboard.md | 11532 | `4fb72425b7ed01cdc5220ad26aeedd75bf2c73695de63e433eaa464cd79e6c6f` |
| wiki-FAQ.md | https://raw.githubusercontent.com/wiki/tmux/tmux/FAQ.md | 18831 | `04c17e622fe7e8042b3c36d2835faf82f32d13e84b73d753988a72f0e80d87e6` |
| wiki-Modifier-Keys.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Modifier-Keys.md | 10883 | `ee3bea1bff2b75d4035da6bc0fd6371840bf274a417e368afa88e0e6c8061fe3` |
| wiki-Formats.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Formats.md | 25050 | `91f16fea64d3691b950ee036422b91d36c6407612dabd381b0a63cf1d220dc19` |
| wiki-Recipes.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Recipes.md | 4877 | `0bfaba8dfcf8a76eeddb2271fa0a7538c5fc671b419bc34440f629d9d11f2bda` |
| wiki-Home.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Home.md | 1238 | `294c6e0c671b6c5a7f48904a960ea2ada7ea9736157ad37e43e60afe54199be9` |
| wiki-Control-Mode.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Control-Mode.md | 10971 | `b604e61bc2874c1af661aafdb97bff258f8328535ab2079fb14339130fab8df0` |
| wiki-Events.md | https://raw.githubusercontent.com/wiki/tmux/tmux/Events.md | 15558 | `7b0f61f57af2a38c71fa073c675746f9afea6616f52b41ec2052e0897d4938c1` |
| README-3.4 | https://raw.githubusercontent.com/tmux/tmux/3.4/README | 2193 | `3c2cc8170bf586d62e67db7a01fff8540ae6b5461f421afe9f0edf0ad466b572` |
| CHANGES-3.8 | https://raw.githubusercontent.com/tmux/tmux/3.8/CHANGES | 180199 | `0be276d0e1f957e21803966ec61d2a696667f9471330a0af269c2473f562c518` |

### zellij (0.46.0: README, change log, default configuration, key presets, layouts; the user documentation)

| Document | Source | Bytes | SHA-256 |
|---|---|---|---|
| README-v0.46.0.md | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/README.md | 6977 | `765503b5e903461ac333a44b07e243a345c6ea02d5df6f202c505784d665d04e` |
| CHANGELOG-v0.46.0.md | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/CHANGELOG.md | 121136 | `b50142100ddf21d3b0b7a8871bde50ed0594c03c92b99f343cffc2c62c84d7ca` |
| config-default-v0.46.0.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/config/default.kdl | 40141 | `9670fce244ec474eb22323e1ffc929c76656bfed59d652c8123d68a08a4245d4` |
| layouts/classic.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/classic.kdl | 265 | `11cb9821f68f544ecf1496b24a5236d4e2783834c111e5afc223820d5be8b8e6` |
| layouts/classic.swap.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/classic.swap.kdl | 3054 | `0d6fceafa6557ce1e95d73500faa7b7aa220f9ad74774dcebab4a08953577973` |
| layouts/compact.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/compact.kdl | 98 | `411e74bcc82cec918e184efdd3d1d5f7acc0b202e47d0af619da049584c6d157` |
| layouts/compact.swap.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/compact.swap.kdl | 2878 | `c088483f729cda3aaa29aea2f57f942775364ef4e54886a5d4346cfb4e97d051` |
| layouts/default.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/default.kdl | 171 | `ebb187207beb2740dfa146e2ea93de69d4157910149aae50b65120f5998f3a52` |
| layouts/default.swap.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/default.swap.kdl | 2953 | `c9b2a0b7e167153ac70d0d049567e1e98d2d1cabf8408acd81fe46a7a8a14c96` |
| layouts/disable-status-bar.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/disable-status-bar.kdl | 94 | `d152866923fa2a971d78d8bfd38ce07ca49d35a5da6b5ec7d82ad601e70bdf2d` |
| layouts/no-plugins.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/no-plugins.kdl | 7 | `61899ed869460a3e206be46224fbc48ec675677828ed3d90b8b9b0e43544f266` |
| layouts/strider.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/strider.kdl | 293 | `3b91f14229d19261e86da5f079b9184813bc30901fd2576a624bafa6f10e65c6` |
| layouts/strider.swap.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/strider.swap.kdl | 3145 | `45fc438e68658a83abf92c9d15326a2c9258e6021704553e92685a2eb04a61c6` |
| layouts/welcome.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/layouts/welcome.kdl | 239 | `9568a08a330cbcd65eea9ada8f36ec43dfa363934c8a6717a7451eba04142d5b` |
| docs/SUMMARY.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/SUMMARY.md | 3756 | `f3a751fd37f9a2a698a7bae66576153dea8de30ad8e2d9d846776e1820b4f9e8` |
| docs/introduction.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/introduction.md | 721 | `570f53205c7b9b42a2e7969eda3ce048643daa5bd07b035da6ce513587ea50ee` |
| docs/overview.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/overview.md | 2529 | `affdb85b80c26a348004c849109146380441bb5ef97ae256b33a3d273f0d5590` |
| docs/installation.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/installation.md | 5053 | `81323e92737ec9a937e1deb2e5ae53d1402937c99255b79d3fad0be4538f631d` |
| docs/integration.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/integration.md | 4243 | `63e15969addad4f3aec5d72c3e155d614bddc00b9172f42430689dc9d2ab4501` |
| docs/compatibility.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/compatibility.md | 9295 | `63968acf44e4537a106362356fd7f85cc9f1952141b52ff4806298cb06eb1afa` |
| docs/faq.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/faq.md | 8555 | `b09b24d37f397af40b3e932de417b4080c0dc7f02cf9114d28efd9ee960789e9` |
| docs/configuration.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/configuration.md | 2995 | `c4b8cdc2bd004158608c3f8b3447cdbceb41f5311d5c792001be110633e03162` |
| docs/options.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/options.md | 31301 | `2dc6d32dc75cc151f937c7537a69dbfd1b7b37702cd215925a94cf5568779abc` |
| docs/keybindings.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybindings.md | 2009 | `5bc73e9d41959ae1ca2de417d686784a8c2b873131bd095916e644d0005772e5` |
| docs/keybindings-modes.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybindings-modes.md | 1752 | `0579e7e600718b933ee5a71ecf1f63e5bb7ea0b71aaeb13e90246b67a9a3f166` |
| docs/keybindings-keys.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybindings-keys.md | 1500 | `fca2a5d830c5d35d4f7f60475db5c4821956ca1ba3653f99065caf50d70e2b40` |
| docs/keybindings-binding.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybindings-binding.md | 1777 | `db4a1dbcf98ada4fd6b8d56e0516c21eea1645edbe7cb97f7d9c56bca4688b3f` |
| docs/keybindings-shared.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybindings-shared.md | 731 | `a3b0ed3acbe07ad8480c951ffc84ee5afaf5349f409811e9406eadd83db31f66` |
| docs/keybindings-possible-actions.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybindings-possible-actions.md | 37329 | `f944bf036c1e5943125028389c63cf65758bc2eb4b7a488e315b126beaa3c01a` |
| docs/keybinding-presets.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/keybinding-presets.md | 9438 | `c73f557325df9a45efd96be2f96d3a362a484b61d4d3dbb0a6f6a299246cb43f` |
| docs/changing-modifiers.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/changing-modifiers.md | 2273 | `e3ea4a56911c767f668492695148cb72ab966fe91bf0e536bf91eb686a09daed` |
| docs/rebinding-keys.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/rebinding-keys.md | 949 | `ef9baa36cb12ce2f524cfa574c8b5961ea9b1e4d27ea62f41086e4ef2016bc0f` |
| docs/mouse-bindings.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/mouse-bindings.md | 9253 | `23e7bf696fb25694ae4ea82c5e6b66ae880a4441f720b11cf82f7f840d9bd882` |
| docs/context-menu.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/context-menu.md | 7758 | `e6e00194e8470c274c44cd1969a2276227cc128aa635d8a9bb879cebcd22f9af` |
| docs/commands.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/commands.md | 8972 | `83069c13d855c6c7f37a8f363e08eb53e476da18704a145d62f15a72e89f7657` |
| docs/command-line-options.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/command-line-options.md | 15846 | `9de4106eb9f4475573dd273342f910a68ae1fb13ba7cae3ed3af9777d67f320d` |
| docs/controlling-zellij-through-cli.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/controlling-zellij-through-cli.md | 2589 | `017f624ad10783d4c30bc390db082c453a15411416082c77ae101944a7a3e46f` |
| docs/cli-actions.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/cli-actions.md | 53288 | `111b5013d4fe3e508d8beee21b01e732930aafd3b93ee52e20b408798958eb92` |
| docs/cli-recipes.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/cli-recipes.md | 25496 | `a0f0be51402358c3738e3b68992e90a9615904dbd3ce0f717d8c55c10247a532` |
| docs/programmatic-control.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/programmatic-control.md | 17696 | `43925b7cfea953af8011265c0899c184fa650252d5ecdb1b85ce7ddb1a31bc66` |
| docs/zellij-run-and-edit.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/zellij-run-and-edit.md | 7997 | `f475e127496649aaf04d3ffb0230315d27731bcb2bd54dc945db6255489973b2` |
| docs/zellij-subscribe.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/zellij-subscribe.md | 4148 | `4ebffe854f8fd56a9891174f99ea33cf623c3e69e8822ce918943f1b0e3c46c8` |
| docs/zellij-terminal.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/zellij-terminal.md | 9866 | `f7db561b9eadeba194982c8f521743b7f58e6776ec388669c5bf0157782ef89b` |
| docs/zellij-plugin-and-pipe.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/zellij-plugin-and-pipe.md | 4582 | `77447eeb55ad60b86beb2e55b507ecea3686ebdd0ed2ea19ac3cc5715078aea9` |
| docs/layouts.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/layouts.md | 2848 | `bb41ba5e3ad2d66d98103e47f0f924034f2b9184d220d0b2d9eca23000def4e6` |
| docs/creating-a-layout.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/creating-a-layout.md | 25659 | `d44a5a0eba905645f999840070cb13441bb541985f75099e34b53029198bbea6` |
| docs/layout-examples.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/layout-examples.md | 5842 | `f5c9b7c1e71064ad9da5638a63fcee0cc97843fbdb7005bed6fec83f949d0273` |
| docs/layouts-templates.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/layouts-templates.md | 2478 | `5a1733333358be0cf300fb89f6a938acf216a96505c459bb26019a69a551ad3f` |
| docs/layouts-with-config.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/layouts-with-config.md | 1483 | `2b9b45b5f5e0a87afe79d2058b67f1edb164ea0ba05f6ea17612c204a29b3ffc` |
| docs/swap-layouts.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/swap-layouts.md | 6328 | `274e769ef0fd9d029e1f026e86c65f8175cf8ca0f94343d1c32a64d4001c9217` |
| docs/session-resurrection.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/session-resurrection.md | 6896 | `f62206e092e2533bc45441931df0a0976a7653ed1ea4bc7afe2c116aef379e7a` |
| docs/session-manager-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/session-manager-alias.md | 3777 | `c5f6ecfa5f20f6ca7ee03aaec871d9589fa4a04b22e17a68e13f0db369fdbb74` |
| docs/session-suggestions.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/session-suggestions.md | 5645 | `5a804117ae8aa8d24ff2ea4aba476f2b0659e2226e19b78740e88684257d96be` |
| docs/nested-sessions.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/nested-sessions.md | 4612 | `d67e3ca4411eec139559aa1187034d65ab408d2c15cb217eac3aa7497bb31dff` |
| docs/terminal-options.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/terminal-options.md | 16303 | `07504fafe3c0d9e4d530d7b8adfcfd9b54a1f3dac43448c81b4bcbba56a36d8d` |
| docs/shell-integration.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/shell-integration.md | 6042 | `1b2a9ecfcddc3f1b30e9c199a30a13423ab970e56aa7c9cc07b428be1ac567a0` |
| docs/status-bar-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/status-bar-alias.md | 1203 | `894dfebebe6f8f72eeba601d2caf0d202ef71b1d538506b018aae75ef4af8236` |
| docs/compact-bar-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/compact-bar-alias.md | 1679 | `2915369d1f2ae30e1e8ba71aaf0c1c8ad31fecc550859ffab3acee549e2b537d` |
| docs/tab-bar-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/tab-bar-alias.md | 2434 | `7c9656c026fc2ea2f885fe361d560ffd315f59f4b066e9193a83e4348fe5c6ee` |
| docs/themes.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/themes.md | 13758 | `0bf721c4941d4605e1db6e17f19db49613a4119c8d06350d4607012cf1e106aa` |
| docs/web-client.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/web-client.md | 13736 | `1d65567a5f2463f8772dab13570d5168fbafd9a6cb125302f013292f9faa5c64` |
| docs/plugins.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/plugins.md | 1291 | `9ee1f1ff28917d37f080f55de8e8d6455d90d0cae2d546b2deab9d5ae56a594e` |
| docs/plugin-overview.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/plugin-overview.md | 913 | `f1f014ba1ba18ff3e5074a093fb620ac9ad0858ce70b7e0a82dc488e6ba8f8bd` |
| docs/plugin-aliases.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/plugin-aliases.md | 3402 | `b2a75cbd2f103e108faf7a44c859fc2482c5543420575a18374234c45a5b48aa` |
| docs/plugin-loading.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/plugin-loading.md | 3016 | `6413a808f7639b901018e3055c1c79291c86c4de8e8d1ad2622b7e03c74a8874` |
| docs/settings-screen.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/settings-screen.md | 3137 | `c59f53bb6cebdee49be36f2b2c1d78d3b2d531e292c4178a3ed238e7f2f4663f` |
| docs/welcome-screen-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/welcome-screen-alias.md | 1027 | `e6ec2f0c69186d1ce9afea3b317282987ad3bd998a971e0213001b4d01cb3092` |
| docs/about-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/about-alias.md | 861 | `3c74133ed2a100b407c78633aa98ecf54e1993bdf4e4427b7b3559480d1c0357` |
| docs/configuration-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/configuration-alias.md | 1632 | `257e0f7329c1fe3a8ec7ed3f87ffb242845aed51fa440876b9525e14e0d8bbb8` |
| docs/desktop-setup.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/desktop-setup.md | 6151 | `87283fbcdeb4ebbda7300d5c0d2fbccf7024c55c4c404dcbd3911c3a2d72fe83` |
| docs/inbox.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/inbox.md | 10384 | `4073f40358f652f47155996e30206fa96134d923f3d92d14700d4df5b1cb2985` |
| docs/inbox-integrations.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/inbox-integrations.md | 7315 | `391aff27ae81b506767b338f289613b422dbf9783332f1eacc430bca7450fe39` |
| docs/zellij-prompt.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/zellij-prompt.md | 12611 | `8fff6eaee1bcd4884e5073a8ec7477f98a29a300a2df585d5bd77fd8786f0a89` |
| docs/prompt-alias.md | https://raw.githubusercontent.com/zellij-org/zellij-org.github.io/main/docs/src/prompt-alias.md | 1038 | `153da6b0788f4a9bc47ce982ca23081b0d7a901425675d3307402269ee4346e8` |
| keybinds/default.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/keybinds/default.kdl | 12333 | `335d78135856cddff71da67249ad88953a97788448a7482db133728f412cb745` |
| keybinds/unlock-first.kdl | https://raw.githubusercontent.com/zellij-org/zellij/v0.46.0/zellij-utils/assets/keybinds/unlock-first.kdl | 11887 | `aea9547662672257881fff0ac69702c58e5e5d2b4e802aee2d9290d9c6596b21` |

### herdr (0.9.5: README, change log, documentation, configuration reference), the project at `herdrdev/herdr`

| Document | Source | Bytes | SHA-256 |
|---|---|---|---|
| README-v0.9.5.md | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/README.md | 5003 | `9b3943664e3c4cf928c1e317f1de632d9a051e59c4b8b6b0e93f1decc43dbb3d` |
| CHANGELOG-v0.9.5.md | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/CHANGELOG.md | 150087 | `634375655c30390c8374809119eff15b7436f2e4d5faeddba65b7c1af97c2d99` |
| docs/index.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/index.mdx | 2774 | `001055a23593e36c4b3f465431a348ad78bc7c896f6dccbc46ea4f6f4b58b310` |
| docs/concepts.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/concepts.mdx | 3568 | `b179d11399a840ed5ee5d8495d7d28d8f095d0672a9bc1767478f3c0abbacb56` |
| docs/quick-start.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/quick-start.mdx | 4654 | `ad3600c3fb4d4aa608bf1bab6048429bb06b5502c1ff9c21d19a326b54957ab1` |
| docs/install.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/install.mdx | 6242 | `2de21bc4fb70be9bc2e6bf20d8c10cb51ed3affe3f257d0736e76316641dac00` |
| docs/how-to-work.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/how-to-work.mdx | 3631 | `c75674e4eebcafd4f734eea0fe6206317ff92a7cd3b0a85bf3e976dccf052b9c` |
| docs/keyboard.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/keyboard.mdx | 8953 | `d495106599b1b766bd27182ca5f07c2d6d8bf6c014b802301bae9712d1aa5561` |
| docs/configuration.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/configuration.mdx | 32947 | `518d388234dbc59628bbefeba4303925fbb1d296ce6d4f68be3d3f340731efb9` |
| docs/config-reference.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/config-reference.mdx | 677 | `2a1e7016bb0f4944f2b1087283cdf87a59637ca4354744baab70e7670d55d8d3` |
| docs/cli-reference.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/cli-reference.mdx | 37574 | `07163713a815e965c245a011d1e72d2be0208afa1e8049f0e091b7982ac87a6e` |
| docs/socket-api.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/socket-api.mdx | 46391 | `1b92d7810e56ae6310f41e318bd771f926e6e8b6a2ce4189e9dfeb4bce9e3d15` |
| docs/session-state.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/session-state.mdx | 9920 | `7d79023cd42d3cdfc39bbba9d875a935bea82c7f5338343089d393f2c7224970` |
| docs/persistence-remote.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/persistence-remote.mdx | 8899 | `e86aca5eb273634ce0a68ce3d335f5be00d89598ceac48fab041c8c37505e478` |
| docs/connecting-machines.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/connecting-machines.mdx | 15116 | `121adb9f30be4061db2b3f41b07f8b2be3b93a17e2de91999ba7fb9380362839` |
| docs/agents.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/agents.mdx | 11690 | `c119ece87db6dc2520204583723f6b655b13810bbea4a179c1a803a0b87b0f3c` |
| docs/agent-automation.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/agent-automation.mdx | 12141 | `dd6c5a1435d36b12cad07aa9ba185d1bb3ead424bc7daccbb34527ba6f0f0808` |
| docs/agent-skill.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/agent-skill.mdx | 2882 | `c0c6b263624856e497b3a9426c98190991f81f296a4d1d3c92ac10b8dff8134e` |
| docs/integrations.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/integrations.mdx | 21274 | `90378dc6e53c9b1f8c23456c285d6e9f210ae2aeb6578c77a9f72b3b3c2889ed` |
| docs/add-herdr-support.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/add-herdr-support.mdx | 5857 | `8e3d60189734d0eac485a2668dde89019d8b7717e7aa2813a593ffb6890a40ad` |
| docs/plugins.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/plugins.mdx | 17372 | `ee9ef20dd41762f33c73ecaa1a194d42f6acf3d92bd35258d586bd79e9fccfea` |
| docs/marketplace.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/marketplace.mdx | 2300 | `9ed9a2ef82577ae78ed92f9d81772d73832745d1fd0f3768a7d23b44074cd464` |
| docs/troubleshooting.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/troubleshooting.mdx | 6965 | `f0219c6ab8b1612170c62e512b8c9c4ac97e9394f6d5fc7c22829ace815080d0` |
| docs/windows-beta.mdx | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/content/docs/windows-beta.mdx | 12318 | `8630377ce26963373cac62d20c700c6d19060671cc2d8096650e0196d67b549b` |
| docs/config-reference.json | https://raw.githubusercontent.com/herdrdev/herdr/v0.9.5/docs/next/website/src/data/config-reference.json | 59081 | `86b27928b1ce20fe20b0a41dc524be9228de0d98ac43ed147064a814cdac35c7` |

## Consulted for protocol v1 (2026-11-12)

| Reference | Identity | Use |
|---|---|---|
| PAX `notes/px125-multiplexer-readiness.md`, documents only | branch px125 at `6c559045`; SHA-256 `0242c786ec81713f1b9d564f4c60cfae6a572b7c48d8a4fa6d0010ff3667db4f` | 4096-byte sockets, pty queues, process slots, terminal and daemon evidence; no kernel source opened |
| wolf-std `std/poll/poll.lu` and all nine `tests/poll/` rows | trunk `be1d10fa2798cc6bc2a1fd0b2e559e283469c9bf`; module SHA-256 `eec27137180e9c818d65054aaf22f69338a787cc3923f32630d3e770a06c5d59` | the actual Waiter surface, its four named unsupported combinations, partial pty writes and hangup posture |
| wolf-std `docs/sc82-one-wait.md` | same commit; SHA-256 `0a42c592f35abcd9f17e4e420bd465ccfb79b685fdce2933a5a94c81865c85d0` | runtime readiness-set/partial-write/peer-credential contracts M1-M3 and the reported evidence boundary |
| warren's public protocol/emulator drafts, SCREEN-DUMP and TERM | starting tree `7f4f3380` | wire layout and server state-machine starting contract; at most two marks per cell |

The protocol lane did not read multiplexers' protocols or any source on the
never-read list. Its codec/model rows open no socket, pty or child process;
existing oracle gates remain black-box binary runs.

## Incidental exposure

None. No file of source code from the never-read list was opened or shown.
Directory listings (names only) of zellij's asset directories and of herdr's
repository root and documentation tree were seen while locating documents.
