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

This is the parser-only slice, not a completed emulator. The final-head
platform and plant records accompany the pull request; they are not claims
of whole-screen agreement.

| Row | Entry or data | What it establishes |
|---|---|---|
| decoder, transitions, caps, every split point | `src/vt_parser_test.lu` | ten decoder fixtures, twenty initial transition fixtures, the measured edge corrections, fixed metadata bounds and chunking |
| hostile input | `src/vt_hostile_test.lu` | eight seeded raw-byte streams, 65,536 ESC bytes, unterminated strings and saturating parameters, each under a 32 KiB region cap |
| state-loss plant | `src/vt_state_test.lu` | losing the parser state between bytes is red at `parser-state-loss`; the one-line break is isolated on `wr01-plant-state-loss-final` |
| reference projection | `src/vt_fixture_test.lu`, `tests/vt/parser_reference.py` | printed scalars and the last title on seventeen identical reference streams; **not** cells, attributes, cursor or modes |
| reference snapshots | `tests/vt/parser-reference/` | nineteen whole-screen snapshots bound by digest to the unchanged oracle pin; two additionally measure a one-row region |
| allocation and throughput | `src/vt_bench_test.lu` | 61,440 mixed bytes, a named region and an isolated feed-loop clock; no clock in the parser |
| existing pure CI entry | `src/pure_test.lu` | UTF-8, CSI and OSC state survives byte-at-a-time calls under the reference interpreter |

### Red before green

- Decoder fixtures at `471d60e` failed their assertion before implementation
  `1501549`.
- Transition fixtures at `afa646c` failed their assertion before implementation
  `0f472e4`.
- The extra non-ASCII escape rows at `f037a75` failed before the measured
  correction at `9c5c6a7`.
- The named-region allocation row at `55ada7a` failed under lupin. Returning
  a fresh token record for every byte charged transient allocations there.
  `96fa912` adds the allocation-free `advance_in_place` form; the value-returning
  convenience form remains available with that cost documented.
- The state-loss plant was observed red by name at its dedicated row.
- **The caps' rows were written after the cap code.** They are covered by
  checks, but this is not a separate observed-red cap implementation series.

### Measurements against the prediction

At checkpoint `7820416`, the macOS repository gate passed thirteen tests on
the checked tier without native fallback. The separate native and lupin
parser, hostile, reference-projection and measurement rows passed.

The native parser charged 6,144 bytes on construction and zero additional
bytes while feeding. Lupin charged 9,360 bytes on construction and zero
additional bytes while feeding. These are tier-specific region charges,
not RSS: the native result meets the provisional 8 KiB estimate; lupin's
representation exceeds it. The fixed logical payload bounds are unchanged.

The isolated native feed loop processed 61,440 bytes in 3,493,250 ns, about
17.6 MB/s against the predicted 5 MB/s. Lupin took 6,984,681,625 ns, about
8.8 kB/s against the predicted 30 kB/s. End-to-end runner time is reported
separately because startup dominates this small native take. A completed
61,440-byte lupin take under its 50,000,000-step ceiling gives a lower bound
of 0.0012288 bytes per evaluation step; the binary exposes no exact successful
step count. Future lupin corpus estimates should use the measured rate,
not the original prediction.

The earlier zero from a live-region query without a named region was not a
memory measurement. The earlier long lupin take exhausted its step ceiling;
it was not silently counted as a pass. The first hostile generator also
needed an explicit `int` RNG to avoid inferred `i32` overflow under lupin.
All these failed takes are retained in the evidence hand-back.

### Agreement and decisions

The seventeen parser projections have sixteen reference agreements and one
named difference, D8: DEL inside a title is dropped rather than changed to
`?`. The reference input is `tests/vt/parser-reference/osc-del.in`; its title
is `613f62`, while the written warren expectation is `6162`. This is an
intentional display-text policy, not a normalisation hidden in comparison.
Non-ASCII scalars inside ESC/CSI abandon the sequence and are discarded,
including intermediate and ignore states; the next bytes are ground text.
The decoder's D3 replacement policy remains a written-expectation row.

A one-row pane has region `1–1`. The corrected G4 invariant and both observed
one-row streams are in the contract and the reference fixtures. No new oracle
fault or undecided divergence is claimed.

There is no grid, whole-screen candidate dump, width sweep, history or PAX
measurement in this slice. D1, D2 and D4–D7 screen behavior is not evaluated.
The 100 MB history soak and larger/nightly fuzz corpus remain later W1 work.
The README and architecture map were refreshed; `src/proto` and
`docs/PROTOCOL.md` were not changed.

## Done-when

- [x] incremental decoder and all ten parser states
- [x] parser cap, finite hostile-input and chunking rows
- [x] state-loss plant red by name
- [ ] full-screen census rows, native Linux and macOS, and lupin
- [ ] grid, modes and answers
- [ ] width sweep and Unicode pin
- [ ] resize and byte-capped history
- [ ] `vt-dump`, complete-screen oracle comparison and first-divergence tool
- [ ] recorded and fuzzed screen agreement, with every difference classified
- [ ] static PAX corpus leg, or the missing harness stated explicitly
