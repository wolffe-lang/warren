#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout of
# a one-hunk plant in the pane rows: the frame after the key list is compared
# with the frame before in every cell, the clock's included. The rows step
# runs the row that keeps the key list open across a minute, which the plant
# must turn red; the recorder checks its FAIL line. The row waits for the
# clock: up to a minute. Its panes run /bin/cat with a home of their own.
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh
mkdir -p "$HOME" "$TMPDIR" target/native
case "${1:-}" in
 build)
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  "$WOLF" build --deny-warnings src/pane_rows.lu -o "$root/target/native/pane-rows"
  ;;
 rows)
  rm -rf target/plant-prows && mkdir -p target/plant-prows && cd target/plant-prows
  exec "$root/target/native/pane-rows" "$root/target/native/warren" help-overlay-minute help-overlay
  ;;
 *) printf 'FAIL help-minute-plant-rig unknown-step\n'; exit 2 ;;
esac
