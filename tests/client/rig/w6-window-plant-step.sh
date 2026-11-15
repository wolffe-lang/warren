#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout of
# a one-hunk plant in the client's window size. The rows step runs the client
# rows the plant must turn red; the recorder checks their FAIL lines. The
# rows' panes run /bin/sh with a home of their own (the rows set them), and
# COLUMNS and LINES are never inherited.
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh
unset COLUMNS LINES
mkdir -p "$HOME" "$TMPDIR" target/native
case "${1:-}" in
 build)
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  "$WOLF" build --deny-warnings src/client_rows.lu -o "$root/target/native/client-rows"
  ;;
 rows)
  rm -rf target/plant-wrows && mkdir -p target/plant-wrows && cd target/plant-wrows
  exec "$root/target/native/client-rows" "$root/target/native/warren" zero-window window-too-large
  ;;
 *) printf 'FAIL w6-window-plant-rig unknown-step\n'; exit 2 ;;
esac
