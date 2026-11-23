#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode on the host, from a committed
# checkout with the pinned toolchain staged in .wolf-bin, beside the engine
# (the environment verbs-step.sh reads: WARREN_ENGINE, WARREN_ORACLE_IMAGE,
# WARREN_CPUS, WARREN_MEMORY).
#   plant ROW   inside the image, this script's `inner ROW`: warren and the
#               pane rows built, then the one pane row a plant must turn red
#               by name (source-applies-live, for a plant whose `source`
#               takes the defaults, not the file's settings): it prints FAIL
#               ROW and ends 1
#   inner ROW   that, from the checkout's root, inside the image
set -euo pipefail
root=$PWD
case "${1:-}" in
 plant)
  engine=${WARREN_ENGINE:?set WARREN_ENGINE}
  case "$engine" in /*) ;; *) printf 'REFUSED engine-path-not-absolute\n'; exit 75 ;; esac
  image=${WARREN_ORACLE_IMAGE:?set WARREN_ORACLE_IMAGE}
  cpus=${WARREN_CPUS:?set WARREN_CPUS}
  memory=${WARREN_MEMORY:-12g}
  export TMPDIR="$root/target/tmp"
  mkdir -p "$root/target/home" "$TMPDIR"
  . tools/container-run.sh
  rc=0
  container_run "$engine" "$memory" "$image" --network=none --userns=keep-id --user 1000:100 --ulimit core=0:0 \
    -v "$root:$root" -w "$root" -e HOME="$root/target/home" -e TMPDIR="$root/target/tmp" -e SHELL=/bin/sh \
    -e PYTHONDONTWRITEBYTECODE=1 -- taskset -c "$cpus" bash tests/vt/rig/pane-plant-step.sh inner "${2:?}" || rc=$?
  exit "$rc"
  ;;
 inner)
  row=${2:?}
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  mkdir -p target/native
  "$WOLF" build --deny-warnings src/warren.lu -o target/native/warren
  "$WOLF" build --deny-warnings src/pane_rows.lu -o target/native/pane-rows
  rm -rf target/plant-prows && mkdir -p target/plant-prows && cd target/plant-prows
  exec ../native/pane-rows ../native/warren "$row"
  ;;
 *) printf 'FAIL pane-plant-rig unknown-step\n'; exit 2 ;;
esac
