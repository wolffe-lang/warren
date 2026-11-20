#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, inside the pinned oracle image,
# from a committed checkout with the pinned toolchain staged in .wolf-bin.
#   gate-linux  the whole Linux gate (it runs the pane capacity rows)
#   build       the pane capacity rows, natively
#   plant       the pane capacity rows, which a plant must turn red at
#               pane-first-resize-keeps-the-ring: the native trap names only
#               its line, so this step names the row the line belongs to
set -euo pipefail
root=$PWD
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh LC_ALL=C.UTF-8 TZ=UTC
mkdir -p "$HOME" "$TMPDIR" target/native
case "${1:-}" in
 gate-linux)
  exec bash tools/gate linux
  ;;
 build)
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/vt/pane_capacity_rows.lu -o "$root/target/native/vt-pane-capacity"
  ;;
 plant)
  rc=0
  out=$("$root/target/native/vt-pane-capacity" 2>&1) || rc=$?
  printf '%s\n' "$out"
  line=$(grep -n 'pane-first-resize-keeps-the-ring' src/vt/pane_capacity_rows.lu | cut -d: -f1)
  if [ "$rc" -ne 0 ] && printf '%s\n' "$out" | grep -q "src/vt/pane_capacity_rows.lu:$line:"; then
    printf 'FAIL pane-first-resize-keeps-the-ring exit=%s %s\n' "$rc" "$(printf '%s\n' "$out" | grep MEASURE | tail -1)"
  fi
  exit "$rc"
  ;;
 *) printf 'FAIL history-ring-rig unknown-step\n'; exit 2 ;;
esac
