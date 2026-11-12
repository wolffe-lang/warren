# The emulator

## Forbidden

The parser is written from the emulator contract and published terminal documents. No terminal emulator, multiplexer, terminal-parsing library, ncurses or kernel implementation is consulted. The reference programs are binaries only. The protocol, server and client are outside this change.

## Inputs verified

The starting commit is `7f4f3380`. The repository's emulator draft, scope prediction, screen-dump specification, census streams, oracle harness and toolchain pins were read before implementation. The pinned tools are wolf 0.2.39, lupin 0.1.61 and wolf-std `77cf3210`.

## Prediction

Committed before implementation.

The module layout will be `src/vt/parser.lu` (incremental UTF-8 and the ten parser states), `vt.lu` (the pane value and dispatch), then separate grid, rendition, width, resize and history modules. Parser actions are consumed immediately, rather than accumulated in a queue chosen by the input. A single-byte parser call returns at most two actions: a replacement for an interrupted UTF-8 prefix and the action for the breaking byte.

The first coherent slice is the parser alone. It does not claim a terminal screen or `vt-dump`. First commit failing rows for the census's malformed UTF-8, C1, cancellation, embedded controls, unknown functions and string termination. Implement decoding and transitions, then cap and chunking rows. The expected green rows are decoder, parser transitions, census token boundaries, all split points, parameter saturation, string and parameter caps, and deterministic hostile input. Native Linux, native macOS and lupin run the same pure checks. A parser-state-loss plant must fail the chunking row.

Next slices implement the grid and modes (the eight complete screen cases and the non-resize census), then resize and history (the resize census, reflow properties and storage accounting), then `vt-dump` and differential replay of the recorded and generated corpus. D1–D7 remain explicit written-expectation rows, not silent oracle normalisations. No screen agreement is claimed for this parser-only slice.

For the eventual grid, a provisional budget of 64 bytes per cell gives 245,760 bytes for two 80×24 screens and 3,686,400 bytes for two 320×90 screens. With the default 8 MiB history cap, these are 8.235 MiB and 11.516 MiB before row headers, parser state, answers and events. These are predictions, not an implementation layout or an RSS claim. History must account its encoded bytes exactly and never allocate the whole cap in advance. The first parser slice will measure its own retained state and process peak separately; it cannot measure a pane that does not yet exist.

Expected parser throughput on one CPU is at least 5 MB/s natively and 30 kB/s under lupin for ASCII mixed with CSI. The retained parser payload should stay below 8 KiB, independent of input length: 32×6 parameter slots, two intermediates, 4096 OSC bytes, and a partial UTF-8 scalar. Runtime container and process overhead are measured separately from that logical payload.

## Evidence index

This is a parser-only work in progress, not a completed emulator or a merge-ready gate. Decoder fixtures were committed at `471d60e` and failed their assertion before the decoder implementation at `1501549`. Transition rows at `afa646c` failed their assertion before the implementation at `0f472e4`. Cap and every-split checks at `110536e` passed natively.

At `a04faca`, the repository's macOS gate passed (eight tests; the long measurement entry fell back from checked execution to native). The parser's own native and lupin entries passed. The separate throughput step failed because lupin exhausted its 50-million-step budget. The native runner measured 983,040 input bytes in 0.234395 seconds, about 4.19 MB/s, below the predicted 5 MB/s. That is end-to-end runner time, including startup, not an isolated inner-loop rate.

The first allocation witness incorrectly queried the live-region counter without creating a named region: its zero was not a retained-memory measurement. The next revision uses a named region and a smaller, 61,440-byte finite take to fit lupin's budget. That revision still needs its recorded run; no corrected memory number is claimed.

Linux execution and additional black-box parser-edge probes are queued. The first wait exceeded the hand-back threshold before either ran. No whole-screen oracle agreement, Linux pass, PAX pass, hostile-input soak or plant result is claimed. The plant and PR remain to be made. The initial fixed-cap implementation and its additional cap checks were committed together with the transition work rather than in a separate observed-red cap series; that gap must not be described as red-first evidence.

The README and architecture map were refreshed for this partial slice. `src/proto` and `docs/PROTOCOL.md` were not changed.

## Done-when

- [ ] incremental decoder and all ten parser states
- [ ] cap, hostile-input and chunking rows
- [ ] census-derived parser rows, native Linux and macOS, and lupin
- [ ] state-loss plant red by name
- [ ] grid, modes and answers
- [ ] width sweep and Unicode pin
- [ ] resize and byte-capped history
- [ ] `vt-dump`, complete-screen oracle comparison and first-divergence tool
- [ ] recorded and fuzzed screen agreement, with every difference classified
- [ ] static PAX corpus leg, or the missing harness stated explicitly
