#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode on the host, from a committed
# checkout with the pinned toolchain staged in .wolf-bin, beside the engine
# (as container-limits-step.sh, whose environment it reads: WARREN_ENGINE,
# WARREN_ORACLE_IMAGE, WARREN_CPUS, WARREN_MEMORY).
#   preflight   the image held to the package list and the binary pins
#   gate-linux  the whole Linux gate inside the image, started by
#               tools/container-run.sh as tools/in-container starts it
#   plant       inside the image, tests/vt/rig/verbs-inner.sh plant: warren
#               and the session rows built, then the row that holds ids never
#               handed out again, which a plant that hands out a freed session
#               id must turn red: it prints FAIL ids-never-reused and ends 1
#   toolchain   inside the image, tests/vt/rig/verbs-inner.sh toolchain: the
#               staged pin found and run as the plant step finds it
set -euo pipefail
root=$PWD
engine=${WARREN_ENGINE:?set WARREN_ENGINE}
case "$engine" in /*) ;; *) printf 'REFUSED engine-path-not-absolute\n'; exit 75 ;; esac
image=${WARREN_ORACLE_IMAGE:?set WARREN_ORACLE_IMAGE}
cpus=${WARREN_CPUS:?set WARREN_CPUS}
memory=${WARREN_MEMORY:-12g}
export TMPDIR="$root/target/tmp"
mkdir -p "$root/target/home" "$TMPDIR"
. tools/container-run.sh
inside() {
  container_run "$engine" "$memory" "$image" --network=none --userns=keep-id --user 1000:100 --ulimit core=0:0 \
    -v "$root:$root" -w "$root" -e HOME="$root/target/home" -e TMPDIR="$root/target/tmp" -e SHELL=/bin/sh \
    -e PYTHONDONTWRITEBYTECODE=1 -e WARREN_FUZZ_PROFILE="${WARREN_FUZZ_PROFILE:-pull-request}" \
    -- taskset -c "$cpus" "$@"
}
case "${1:-}" in
 preflight)
  printf 'IMAGE %s id=%s\n' "$image" "$("$engine" image inspect "$image" --format '{{.Id}}')"
  for pair in oracle-packages.txt:ci/packages.txt oracle-binaries.txt:ci/oracle-binaries.lock; do
    "$engine" run --rm --network=none --memory 256m --memory-swap 256m "$image" cat "/opt/${pair%%:*}" \
      | diff -u "${pair#*:}" -
  done
  printf 'PASS verbs-preflight image-pins engine=%s\n' "$engine"
  ;;
 gate-linux)
  printf 'IMAGE %s cpus=%s memory=%s\n' "$image" "$cpus" "$memory"
  rc=0
  inside bash tools/gate linux || rc=$?
  exit "$rc"
  ;;
 plant)
  rc=0
  inside bash tests/vt/rig/verbs-inner.sh plant || rc=$?
  exit "$rc"
  ;;
 toolchain)
  rc=0
  inside bash tests/vt/rig/verbs-inner.sh toolchain || rc=$?
  exit "$rc"
  ;;
 *) printf 'FAIL verbs-rig unknown-step\n'; exit 2 ;;
esac
