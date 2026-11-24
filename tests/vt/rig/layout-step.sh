#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode on the host, from a committed
# checkout with the pinned toolchain staged in .wolf-bin, beside the engine
# (as verbs-step.sh, whose environment it reads: WARREN_ENGINE,
# WARREN_ORACLE_IMAGE, WARREN_CPUS, WARREN_MEMORY).
#   plant   inside the image, this script's `rows` mode: the plant must turn
#           the layout file round trip red by name at layout-file-round-trip
#   rows    (inside the image) the version member generated first, as the
#           gate's version-generation step does, then src/layout_file_rows.lu
#           built and run natively: 2000 sequences at each size
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
    -e PYTHONDONTWRITEBYTECODE=1 -- taskset -c "$cpus" bash tests/vt/rig/layout-step.sh rows || rc=$?
  exit "$rc"
  ;;
 rows)
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  mkdir -p target/native
  "$WOLF" build --deny-warnings src/layout_file_rows.lu -o "$root/target/native/layout-file-rows"
  exec "$root/target/native/layout-file-rows"
  ;;
 *) printf 'FAIL layout-rig unknown-step\n'; exit 2 ;;
esac
