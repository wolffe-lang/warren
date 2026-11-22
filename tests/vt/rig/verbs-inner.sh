#!/usr/bin/env bash
# Run from a checkout's root: inside the pinned image by verbs-step.sh, or
# natively on a host with the pinned toolchain staged in .wolf-bin.
#   toolchain  the staged pin found as every step finds it, and its wolf and
#              lupin run: the check a record makes before it waits for a host
#   plant ROW  warren and the session rows built, then the one session row a
#              plant must turn red by name (it prints FAIL ROW and ends 1):
#              ids-never-reused, split-prints-new-id
set -euo pipefail
root=$PWD
. tools/toolchain-env.sh
case "${1:-}" in
 toolchain)
  "$WOLF" --version
  "$LUPIN" --version
  printf 'PASS verbs-toolchain stage=%s std=%s\n' "${WARREN_TOOLCHAIN_DIR:-$root/.wolf-bin}" "$(cat "$WOLF_STD/STD-REV")"
  ;;
 plant)
  row=${2:?}
  python3 -I tools/vt/generate_version.py
  mkdir -p target/native
  "$WOLF" build --deny-warnings src/warren.lu -o target/native/warren
  "$WOLF" build --deny-warnings src/session_rows.lu -o target/native/session-rows
  rm -rf target/plant-rows && mkdir -p target/plant-rows && cd target/plant-rows
  exec ../native/session-rows ../native/warren "$row"
  ;;
 *) printf 'FAIL verbs-inner unknown-step\n'; exit 2 ;;
esac
