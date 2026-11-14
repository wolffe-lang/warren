#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout of
# a one-hunk plant in the client. The rows step runs the renderer's rows; the
# recorder checks the FAIL line the plant must produce.
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
export HOME="$root/target/home" TMPDIR="$root/target/tmp"
mkdir -p "$HOME" "$TMPDIR"
case "${1:-}" in
 build)
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  ;;
 rows)
  rc=0
  "$WOLF" test --deny-warnings src/client_render_test.lu > target/client-render.out 2>&1 || rc=$?
  cat target/client-render.out
  if grep -q 'test_console_policy ... FAILED' target/client-render.out; then
    printf 'FAIL console-policy the console no longer keeps every glyph in its column\n'
  fi
  exit "$rc"
  ;;
 *) printf 'FAIL w2-client-plant-rig unknown-step\n'; exit 2 ;;
esac
