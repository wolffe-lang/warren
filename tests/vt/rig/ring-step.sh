#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode on the host, from a committed
# checkout with the pinned toolchain staged in .wolf-bin, beside the engine
# (as verbs-step.sh, whose environment it reads: WARREN_ENGINE,
# WARREN_ORACLE_IMAGE, WARREN_CPUS, WARREN_MEMORY).
#   plant   inside the image, this script's `rows` mode: the plant must turn
#           the ring rows red by name at ring-resident-new
#   rows    (inside the image) the version member generated first, as the
#           gate's version-generation step does, measure-child and ring-probe
#           built as the gate builds them, then tests/vt/ring_resident_rows.py
#           held to the takes recorded for this host
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
    -e PYTHONDONTWRITEBYTECODE=1 -- taskset -c "$cpus" bash tests/vt/rig/ring-step.sh rows || rc=$?
  exit "$rc"
  ;;
 rows)
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  mkdir -p target/native
  cc -std=c11 -O2 -Wall -Wextra -Werror tools/vt/measure_child.c -o "$root/target/native/measure-child"
  "$WOLF" build --deny-warnings src/ring_probe.lu -o "$root/target/native/ring-probe"
  exec python3 -I tests/vt/ring_resident_rows.py "$root/target/native/measure-child" "$root/target/native/ring-probe"
  ;;
 *) printf 'FAIL ring-rig unknown-step\n'; exit 2 ;;
esac
