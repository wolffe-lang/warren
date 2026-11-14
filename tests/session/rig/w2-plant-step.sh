#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout of
# a one-hunk plant in the server. The rows step names the rows the plant must
# turn red; the recorder checks their FAIL lines.
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
export HOME="$root/target/home" TMPDIR="$root/target/tmp"
mkdir -p "$HOME" "$TMPDIR" target/native
case "${1:-}" in
 build)
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  "$WOLF" build --deny-warnings src/session_rows.lu -o "$root/target/native/session-rows"
  ;;
 rows)
  rm -rf target/plant-rows && mkdir -p target/plant-rows && cd target/plant-rows
  exec "$root/target/native/session-rows" "$root/target/native/warren" never-ack-beside-active resize-crossing-image
  ;;
 *) printf 'FAIL w2-plant-rig unknown-step\n'; exit 2 ;;
esac
