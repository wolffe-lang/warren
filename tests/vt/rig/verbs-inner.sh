#!/usr/bin/env bash
# Run from a checkout's root: inside the pinned image by verbs-step.sh, or
# natively on a host with the pinned toolchain staged in .wolf-bin.
#   toolchain  the staged pin found as every step finds it, and its wolf and
#              lupin run: the check a record makes before it waits for a host
#   plant      warren and the session rows built, then the row that holds ids
#              never handed out again; a plant that hands out a freed session
#              id prints FAIL ids-never-reused and ends 1
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
  python3 -I tools/vt/generate_version.py
  mkdir -p target/native
  "$WOLF" build --deny-warnings src/warren.lu -o target/native/warren
  "$WOLF" build --deny-warnings src/session_rows.lu -o target/native/session-rows
  rm -rf target/plant-rows && mkdir -p target/plant-rows && cd target/plant-rows
  exec ../native/session-rows ../native/warren ids-never-reused
  ;;
 *) printf 'FAIL verbs-inner unknown-step\n'; exit 2 ;;
esac
