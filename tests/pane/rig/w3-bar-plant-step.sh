#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout of
# a one-hunk plant in the server's tab marks. The rows step runs the pane rows
# the plant must turn red; the recorder checks their FAIL lines. The rows'
# panes run /bin/sh with a home of their own (the rows set them).
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
  rm -rf target/plant-brows && mkdir -p target/plant-brows && cd target/plant-brows
  exec "$root/target/native/pane-rows" "$root/target/native/warren" activity-marks zoom-mark
  ;;
 *) printf 'FAIL w3-bar-plant-rig unknown-step\n'; exit 2 ;;
esac
