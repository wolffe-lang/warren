#!/usr/bin/env bash
# The layout lane's recorder steps. The recorder runs them from a committed
# checkout with the pinned toolchain staged in .wolf-bin.
set -euo pipefail
root=$PWD
mode=${1:?mode}
mkdir -p target/layout target/tmp target/home
export TMPDIR="$root/target/tmp" HOME="$root/target/home" LC_ALL=C TZ=UTC
if [ "$mode" = gate-linux ]; then exec bash tools/gate linux; fi
. tools/toolchain-env.sh
case "$mode" in
  native)
    "$WOLF" build --deny-warnings src/layout_native.lu -o "$root/target/layout/native"
    exec "$root/target/layout/native"
    ;;
  checked|lupin) exec python3 -I "${GAUNTLET_RIG_DIR:?}/slices.py" "$mode" ;;
  *) printf 'FAIL layout-rig unknown-mode=%s\n' "$mode"; exit 2 ;;
esac
