#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode on the host, from a committed
# checkout with the pinned toolchain staged in .wolf-bin, beside the engine.
# The recorder runs outside any container here because a row below starts
# containers of its own; the gate runs inside the pinned oracle image.
#   WARREN_ENGINE         the engine, an absolute path
#   WARREN_ORACLE_IMAGE   the pinned oracle image, by id
#   WARREN_CPUS           the take's CPUs, as taskset spells them
#   WARREN_MEMORY         the gate container's limit (default 12g)
#   WARREN_LIMITS_MEMORY  the limit the container rows hold (default 2g; the
#                         memory row touches it and 1 GiB more)
# Steps:
#   preflight   the image held to the package list and the binary pins
#   gate-linux  the whole Linux gate inside the image, started by
#               tools/container-run.sh as tools/in-container starts it
#   limits      tools/container-rows: the memory cap and the signal mask
#   plant       the same rows on a plant whose one hunk drops the swap bound:
#               it prints FAIL container-memory-cap and ends 1
set -euo pipefail
root=$PWD
engine=${WARREN_ENGINE:?set WARREN_ENGINE}
case "$engine" in /*) ;; *) printf 'REFUSED engine-path-not-absolute\n'; exit 75 ;; esac
image=${WARREN_ORACLE_IMAGE:?set WARREN_ORACLE_IMAGE}
cpus=${WARREN_CPUS:?set WARREN_CPUS}
memory=${WARREN_MEMORY:-12g}
limits=${WARREN_LIMITS_MEMORY:-2g}
export TMPDIR="$root/target/tmp"
mkdir -p "$root/target/home" "$TMPDIR"
. tools/container-run.sh
case "${1:-}" in
 preflight)
  printf 'IMAGE %s id=%s\n' "$image" "$("$engine" image inspect "$image" --format '{{.Id}}')"
  for pair in oracle-packages.txt:ci/packages.txt oracle-binaries.txt:ci/oracle-binaries.lock; do
    "$engine" run --rm --network=none --memory 256m --memory-swap 256m "$image" cat "/opt/${pair%%:*}" \
      | diff -u "${pair#*:}" -
  done
  printf 'PASS container-limits-preflight image-pins engine=%s\n' "$engine"
  ;;
 gate-linux)
  printf 'IMAGE %s id=%s cpus=%s memory=%s\n' "$image" "$("$engine" image inspect "$image" --format '{{.Id}}')" "$cpus" "$memory"
  exec_rc=0
  container_run "$engine" "$memory" "$image" --network=none --userns=keep-id --user 1000:100 --ulimit core=0:0 \
    -v "$root:$root" -w "$root" -e HOME="$root/target/home" -e TMPDIR="$root/target/tmp" -e SHELL=/bin/sh \
    -e PYTHONDONTWRITEBYTECODE=1 -e WARREN_FUZZ_PROFILE="${WARREN_FUZZ_PROFILE:-pull-request}" \
    -- taskset -c "$cpus" bash tools/gate linux || exec_rc=$?
  exit "$exec_rc"
  ;;
 limits|plant)
  exec bash tools/container-rows "$engine" "$limits" "$image"
  ;;
 *) printf 'FAIL container-limits-rig unknown-step\n'; exit 2 ;;
esac
