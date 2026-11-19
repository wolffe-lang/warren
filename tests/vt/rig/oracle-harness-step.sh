#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout,
# inside the preflighted pinned image. A take for a change to the oracle
# harness: `unit` is the unit gate (the harness's own rows, the display retry
# rows among them); `oracle` builds warren and the corpus properties and runs
# every gate step that launches the pinned reference terminal, through the
# harness's launch and retry; `plant` and `bound-plant` run the display retry
# rows, `nightly-plant` the tier tests, `known-plant` the fresh drive's
# known-failure rows, `jump-plant` the jump-scroll rows and `reset-plant` the
# display-reset rows (both launch the pinned reference terminal), on a plant
# and name the row it must turn red.
set -euo pipefail
root=$PWD
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh
mkdir -p "$HOME" "$TMPDIR" target/native target/gate
case "${1:-}" in
 unit)
  exec bash tools/gate unit
  ;;
 oracle)
  . "$root/tools/toolchain-env.sh"
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  "$WOLF" build --deny-warnings src/vt/corpus_properties.lu -o "$root/target/native/corpus-properties"
  export LC_ALL=C.UTF-8
  work=target/oracle
  rm -rf "$work" && mkdir -p "$work/fuzz"
  rc=0
  run() {
    local name=$1 start=$SECONDS one=0
    shift
    printf 'START %s\n' "$name"
    "$@" || one=$?
    printf 'END %s exit=%s secs=%s\n' "$name" "$one" "$((SECONDS-start))"
    [ "$one" -eq 0 ] || rc=1
  }
  run display-reset-rows python3 -I tests/vt/display_reset_rows.py
  run case-streams python3 -I tests/vt/cases.py "$work/cases"
  run oracle-cases python3 -I tools/oracle/run.py cases "$work/cases" --expected tests/vt/expected --out "$work/cases-out"
  run jump-scroll-rows python3 -I tests/vt/jump_scroll_rows.py
  run oracle-mutations python3 -I tools/oracle/run.py mutations "$work/cases" --out "$work/cases-out"
  run census-streams python3 -I tests/vt/census.py "$work/census"
  run oracle-census python3 -I tools/oracle/run.py digests "$work/census" --out "$work/census-out" --manifest tests/vt/census.sha256
  run fuzz-streams python3 -I tools/corpus/fuzz.py --digests 32 2048 --dir "$work/fuzz"
  run oracle-fuzz python3 -I tools/oracle/run.py digests "$work/fuzz" --out "$work/fuzz-out" --manifest tests/corpus/fuzz-screens.sha256
  run oracle-corpus python3 -I tools/oracle/run.py digests tests/corpus --out "$work/corpus-out" --manifest tests/corpus/recording-screens.sha256
  run fresh-fuzz-native python3 -I tests/vt/fresh_fuzz.py --profile pull-request --out "$work/fresh-fuzz" "$root/target/native/warren" "$root/target/native/corpus-properties"
  run fresh-fuzz-wide-break python3 -I tests/vt/fresh_fuzz.py --profile nightly --case fresh-0901 --case fresh-2265 --case fresh-2536 --out "$work/fresh-wide-break" "$root/target/native/warren" "$root/target/native/corpus-properties"
  exit "$rc"
  ;;
 plant)
  rc=0
  python3 -I tests/vt/display_retry_rows.py > target/gate/plant-retry-rows.out 2>&1 || rc=$?
  sed 's/^/  /' target/gate/plant-retry-rows.out
  if grep -q '^FAIL display-retry signal-once-then-answers' target/gate/plant-retry-rows.out; then
    printf 'FAIL signal-retry a reference terminal that died on a signal before answering was not retried\n'
  fi
  exit "$rc"
  ;;
 bound-plant)
  rc=0
  python3 -I tests/vt/display_retry_rows.py > target/gate/plant-bound-rows.out 2>&1 || rc=$?
  sed 's/^/  /' target/gate/plant-bound-rows.out
  if grep -q '^FAIL display-retry rate-bound-ordinary-runner' target/gate/plant-bound-rows.out; then
    printf 'FAIL retry-bound an ordinary hosted runner (9 retries in 613 launches) was held past the retry bound\n'
  fi
  exit "$rc"
  ;;
 nightly-plant)
  rc=0
  python3 -I ci/tiers-test.py > target/gate/plant-tiers.out 2>&1 || rc=$?
  sed 's/^/  /' target/gate/plant-tiers.out
  if grep -q '^FAIL: test_nightly_fits_its_limit' target/gate/plant-tiers.out; then
    printf 'FAIL nightly-limit the nightly profile no longer fits twice within its step limit\n'
  fi
  exit "$rc"
  ;;
 known-plant)
  rc=0
  python3 -I tests/vt/fresh_known_rows.py > target/gate/plant-known-rows.out 2>&1 || rc=$?
  sed 's/^/  /' target/gate/plant-known-rows.out
  if grep -q '^FAIL fresh-known known-passes' target/gate/plant-known-rows.out; then
    printf 'FAIL known-fixed a known seed that passes was not held red until it leaves the list\n'
  fi
  exit "$rc"
  ;;
 jump-plant)
  rc=0
  export LC_ALL=C.UTF-8
  python3 -I tests/vt/jump_scroll_rows.py > target/gate/plant-jump-rows.out 2>&1 || rc=$?
  sed 's/^/  /' target/gate/plant-jump-rows.out
  if grep -q '^FAIL jump-scroll erase-on-a-scroll-made-row-counts-written' target/gate/plant-jump-rows.out; then
    printf 'FAIL jump-scroll-off an erase on a scroll-made row did not count its cells as written\n'
  fi
  exit "$rc"
  ;;
 reset-plant)
  rc=0
  export LC_ALL=C.UTF-8
  python3 -I tests/vt/display_reset_rows.py > target/gate/plant-reset-rows.out 2>&1 || rc=$?
  sed 's/^/  /' target/gate/plant-reset-rows.out
  if grep -q '^FAIL display-reset server-keeps-its-state' target/gate/plant-reset-rows.out; then
    printf 'FAIL display-noreset the oracle started its X server without -noreset\n'
  fi
  exit "$rc"
  ;;
 *) printf 'FAIL oracle-harness-rig unknown-step\n'; exit 2 ;;
esac
