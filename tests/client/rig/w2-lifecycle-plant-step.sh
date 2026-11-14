#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout of
# a one-hunk plant in the server's session sizing. The rows step runs the
# client rows the plant must turn red; the recorder checks their FAIL lines.
# The rows' panes run /bin/sh with a home of their own (the rows set them).
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh
mkdir -p "$HOME" "$TMPDIR" target/native
case "${1:-}" in
 build)
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  "$WOLF" build --deny-warnings src/client_rows.lu -o "$root/target/native/client-rows"
  ;;
 rows)
  rm -rf target/plant-crows && mkdir -p target/plant-crows && cd target/plant-crows
  exec "$root/target/native/client-rows" "$root/target/native/warren" second-client
  ;;
 *) printf 'FAIL w2-lifecycle-plant-rig unknown-step\n'; exit 2 ;;
esac
