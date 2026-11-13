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

For the eventual grid, the original provisional budget of 64 bytes per cell gives 245,760 bytes for two 80×24 screens and 3,686,400 bytes for two 320×90 screens. With the default 8 MiB history cap, these are 8.234 MiB and 11.516 MiB before row headers, parser state, answers and events. These are the original payload predictions, not RSS or complete-pane measurements. The initial intention not to preallocate the history cap was superseded by the adopted fixed-byte-ring model; the grid checkpoint below records its actual charges. The parser slice measured its own state and process peak separately.

Expected parser throughput on one CPU is at least 5 MB/s natively and 30 kB/s under lupin for ASCII mixed with CSI. The retained parser payload should stay below 8 KiB, independent of input length: 32×6 parameter slots, two intermediates, 4096 OSC bytes, and a partial UTF-8 scalar. Runtime container and process overhead are measured separately from that logical payload.

## Evidence index

This is the parser-only slice, not a completed emulator. The final-head
platform and plant records accompany the pull request; they are not claims
of whole-screen agreement. The original `d966f49` records are retained as
historical evidence. After the protocol work reached trunk at `5bbc399`,
this slice was rebased without changing any parser or parser-fixture bytes;
README and MAP preserve both implementations' status. A fresh exact-head
record is required for the rebased pull request.

| Row | Entry or data | What it establishes |
|---|---|---|
| decoder, transitions, caps, every split point | `src/vt_parser_test.lu` | ten decoder fixtures, twenty initial transition fixtures, the measured edge corrections, fixed metadata bounds and chunking |
| hostile input | `src/vt_hostile_test.lu` | eight seeded raw-byte streams, 65,536 ESC bytes, unterminated strings and saturating parameters, each under a 32 KiB region cap |
| state-loss plant | `src/vt_state_test.lu` | losing the parser state between bytes is red at `parser-state-loss`; the one-line break is isolated on `wr01-plant-state-loss-rebased` |
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

## D9: post-restore inverse colour cache

The pinned reference can revive a pre-restore background after a saved pen is
restored and the next eligible SGR contains 7 or 27. The trigger is measured
at control-sequence granularity: no separate colour SGR intervenes; foreground
parameters in that same triggering sequence are allowed in any position.
A triggering sequence that also sets a background is outside the measured
D9 divergence for all twenty controls: 7/27 × extended/basic/bright palette,
default or RGB × either parameter order. The explicit background setter wins
in both orders; no broader unmeasured grammar is inferred.

Minimal body, omitting the fixture's title/shape setup:

```
ESC 7   CSI 48;5;181 m   ESC 8   CSI 27 m   X
hex: 1b37 1b5b34383b353b3138316d 1b38 1b5b32376d 58
```

The reference reports X with `bg=idx:181`; its direct SGR status report is
`DCS 1$r 0;48:5:181m ST`. Warren's independently constructed complete
expectation has X with the restored default background and no attributes.
Native matches that frame. With saved explicit palette background 0 and an
intervening RGB(237,31,126), the reference instead revives the RGB integer as
invalid palette entry 15540094. This is not a colour rule warren copies.
**D9 keeps the restored colour value and its set form; 7/27 change only
inverse, never the colours.** The raw twelve-case observations and independent
written frames are separate under `tests/vt/reference/inverse`: eight
one-background-field divergences and four matching controls.

For original fuzz streams 10, 16 and 19, an approved repaired-reference
fixture uses an independent background-only specification tracer. It injects
the restored background value/form immediately after restores into separate
input bytes; the pinned reference constructs every expected cell. Native
original and native repaired replay must both equal the complete expected
frame. Original versus repaired reference is bound to the exact declared
background cells (6, 1903 and 19 respectively), field and corrected value;
any other change is red. No candidate output becomes a golden, and no field
is ignored or comparator widened. The tracer has its own no-injection,
default/palette/RGB, foreground-argument and per-screen-cache rows. The frozen
37-case acquisition has zero capture errors: twelve repaired minimal frames,
three repaired complex frames, twenty mixed-background controls and two
bright-blue report measurements. All 74 native original/repaired replays at
`f4b660b` equal their independent complete frames. Seed 19 additionally has the
source-proved, explicitly LIMITED column-one tab report described below.
`tools/vt/check_d9.py` checks input/tracer/pin bindings, raw evidence hashes
twice, exact background cell/field/value bounds and independent minimal frames.

### Source-bounded report limits

The frozen baseline has seven LIMITED streams, never strict oracle passes.
Seeds 3 and 22 set bright palette 9 and 10 respectively without ever setting
their low counterpart; all declared foreground palettes and non-ambiguous
RGB forms are checked before constructing the complete written frame.
The printer folds those bold foregrounds to 1 and 2. Quarry's resize checkpoint
similarly declares foreground palette exactly `{0,11,12,14}`, making its bold
blue 12 unambiguous despite the reported 4.

Seeds 15, 19, 20, 24 and 29 have literal column-one HTS witnesses: CPL then EL,
CR then BS, CR then IL, and CR/LF respectively. No later clear may invalidate
the witness. Seed 20's sole later current-stop clear is independently anchored
by CHA0 followed by twenty ASCII columns and two fullwidth glyphs: column 25,
not 1. Altered or ambiguous source witnesses are red. The complete written
frame adds only that source-proved stop; all other fields still compare.
The report fixture independently measures HTS at column 1, which DECTABSR
omits. The named limits are `RPT-TABS-COLUMN-ONE` and
`RPT-BRIGHT-BOLD-COLOUR`, with mutation/refusal rows in `report_form_rows.py`.

## D10: combining mark on an unwritten cell

Exact trigger: a combining mark whose target base is unwritten, including an
untouched or erased blank and an addressed last-column blank, on either screen.
At the first column no left-hand cell exists: warren retains its explicit rule
that drops that mark. Otherwise the target becomes written and the extent
includes its full width; resize must preserve it. A wide glyph's trailing half
resolves to its lead, and a pending last-column glyph remains the target.

The eight-case pinned-reference bundle produced six named report failures and
two strict controls. For blank CUP(1,5) + U+0301, pass A prints no written cells
(extent 0), but the full-cell print contains space+acute at row1 column5, beyond
that extent. After resize from 12×2 to 6×4, the full-cell print **keeps the acute
at row1 column5**, while A still prints only empty rows. This is an observation
of the reference's full-cell print, not a replacement complete reference frame.
The strict validator rejects both captures and all four analogous report cases;
it is unchanged. The raw failed inputs, A/S replies and prints remain under
`tests/vt/reference/combining`. Wide-tail and pending-last-column controls remain
strict reference agreements apart from the separately named D7 mode report.

The six expected complete frames are built independently from the printing,
G6 and R1 contract in `combining_expected.py`; no candidate output is read.
Non-cell metadata is additionally checked against the raw reference queries.
`check_combining.py` reproduces each exact strict rejection from frozen evidence,
checks every evidence hash twice and verifies the two complete strict controls.
Red-first `5021b75` independently failed primary/alternate extent and lost-mark
resize rows; `cfe02f2` makes `combine_cell` set writtenness and extend the extent.
The full post-correction rerun is pending. Its first attempt passed the 188
frozen native frames and checked rows, then exposed a fixture metadata mistake:
mode47's shared-screen queries report 47/1047/1049 all set, not independent bits.
That expectation was corrected from the raw reference A replies, not the native
frame; the failed take remains recorded.

## Grid follow-on resource checkpoint

The following are measured constructor region charges at `7450229`, asserted
by the named entries. They include the pane's fixed buffers and initial
resize state, before growing resize-only workspaces. They are not RSS or a
bound on all future retained growth. The former 56-byte cell now has a scalar
written bit and a measured 64-byte native payload; it preserves erased gaps
through later edits and snapshots without changing history's logical format
or the wire. `src/vt/cell_capacity_rows.lu` cancels allocator alignment with
even cell counts and asserts that payload.

| Tier / pane | History cap | Charged bytes | Asserting entry |
|---|---:|---:|---|
| native 80×24 | 0 | 268032 | `src/vt/pane_capacity_rows.lu` |
| native 80×24 | 4096 | 272128 | same |
| native 80×24 | 8388608 | 8656640 | same |
| native 320×90 | 0 | 3713264 | same |
| native 320×90 | 8388608 | 12101872 | same |
| lupin 80×24 | 4096 | 781904 | `src/vt/pane_ledger_rows.lu` |

The ring alone is unchanged: native default storage charges 8388656 bytes,
asserted by `history_capacity_rows.lu`. Lupin's ring ledger remains 16 bytes
per configured slot plus 176 fixed bytes (`history_ledger_rows.lu`). No
interpreter cap is raised and no default-8MiB interpreter pane is claimed.
The separate 4096-byte feed smoke retains zero additional pane charge in
both tiers. `copy_rows.lu` holds independent scalar Cell copies to zero
allocation over 1024 turns in both tiers. The full 100000000-byte native
feed/RSS witness is prepared, not yet run; small smoke timings do not stand
in for it. At `7450229`, den's unseeded and seeded full interpreter replays
both completed under the unchanged 50000000-step and memory limits, with the
title-only proof and whole-screen comparison passing. They took roughly
550 seconds each; this is not a claim of improved wall-clock throughput.
The remaining full-recording interpreter takes are still pending.

At `4737ff8`, all eight full cases, 151 census inputs and five seeded
recording comparisons passed natively; the recording setup retained its paired
unseeded-title-only proof. At `f4b660b`, all 188 frozen streams pass complete
frames under the explicit named policies above: nine previously non-matching
fuzz streams are resolved as D9 and/or source-bounded report limits, not silently
called reference agreements. The complete macOS gate at `f4b660b` passed:
14 explicit checked-machine entries, aggregate 71 tests (69 checked and two
named native fallbacks), complete native/CLI/census/recording comparisons,
bytewise/random P2 and corpus-wide primary R1/R3/R8 properties, native width
vector, private capacity/codec/resize rows and their declared interpreter legs.
Fresh 200×4096-byte fuzz, reference widths and the full resource take remain
separate pending evidence.

> PAX corpus leg: not run, no boot fixture in this repository yet

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
