#!/usr/bin/env bash
# The row returns the actual planted failure; the recorder validates its FAIL.
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
case "${1:-}" in
 build)
  python3 -I tools/vt/generate_version.py
  mkdir -p target/canonical-plant target/plant
  "$WOLF" build --deny-warnings src/vt_scalar_test.lu -o "$root/target/canonical-plant/vt-scalar-plant"
  ;;
 row)
  rc=0
  "$root/target/canonical-plant/vt-scalar-plant" > target/plant/scalar.stdout 2> target/plant/scalar.stderr || rc=$?
  if [ "$rc" -eq 134 ]; then
   python3 -I - <<'PY'
from pathlib import Path
errors = Path('target/plant/scalar.stderr').read_text()
assert 'wolf-trap: assert' in errors and 'src/vt_scalar_test.lu' in errors, errors
PY
   printf 'FAIL vt-scalar-value planted-grid-scalar-substitution exit=%d\n' "$rc"
  elif [ "$rc" -eq 0 ]; then
   printf 'PASS vt-scalar-value plant-was-not-detected\n'
  else
   printf 'FAIL vt-scalar-plant-unexpected-exit exit=%d expected=134\n' "$rc"
  fi
  exit "$rc"
  ;;
 *) printf 'FAIL w1-plant-rig unknown-step\n'; exit 2 ;;
esac
