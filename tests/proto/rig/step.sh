#!/usr/bin/env bash
# Module-specific recorder steps. The checkout is a committed snapshot.
set -euo pipefail
root=$PWD
mode=$1
mkdir -p target/proto target/tmp target/home
export TMPDIR="$root/target/tmp" HOME="$root/target/home"
export LC_ALL=C TZ=UTC
if [ "${WARREN_IN_CONTAINER:-0}" != 1 ] && [ "${WARREN_USE_CONTAINER:-0}" = 1 ]; then
  exec "${WARREN_ENGINE:?set WARREN_ENGINE}" run --rm --network=host --memory 12g --pids-limit 256 \
    -v "$root:$root" -w "$root" -e WARREN_IN_CONTAINER=1 \
    -e TMPDIR="$root/target/tmp" -e HOME="$root/target/home" \
    localhost/wr02-oracle:1 taskset -c "${WARREN_CPUS:?set WARREN_CPUS}" \
    bash tests/proto/rig/step.sh "$mode"
fi
if [ "$mode" = gate-macos ]; then exec bash tools/gate macos; fi
if [ "$mode" = gate-linux ]; then exec bash tools/gate linux; fi
. tools/toolchain-env.sh
case "$mode" in
  native)
    "$WOLF" build --deny-warnings src/protocol_rows.lu -o "$root/target/proto/rows"
    exec "$root/target/proto/rows"
    ;;
  checked)
    "$WOLF" conform-run src/protocol_small.lu --phase=run --checked --json --deny-warnings > target/proto/checked.json
    python3 -I tests/proto/rig/observation.py target/proto/checked.json
    ;;
  lupin) exec "$LUPIN" run src/protocol_small.lu ;;
  fuzz)
    "$WOLF" build --deny-warnings src/protocol_fuzz.lu -o "$root/target/proto/fuzz"
    exec "$root/target/proto/fuzz"
    ;;
  *) printf 'FAIL proto-rig unknown-mode=%s\n' "$mode"; exit 2 ;;
esac
