#!/usr/bin/env bash
# Emulator-only module take, inside the pinned oracle image.
set -euo pipefail
root=$PWD
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh LC_ALL=C.UTF-8 TZ=UTC
mkdir -p "$HOME" "$TMPDIR" target/native target/gate
case "${1:-}" in
 pins)
  diff -u ci/packages.txt /opt/oracle-packages.txt
  diff -u ci/oracle-binaries.lock /opt/oracle-binaries.txt
  while IFS='|' read -r name version want binary; do
    first=$(sha256sum "$binary"); first=${first%% *}
    second=$(sha256sum "$binary"); second=${second%% *}
    [ "$first" = "$want" ] && [ "$second" = "$want" ]
    printf 'PASS oracle-pin %s sha256=%s read-twice\n' "$name" "$first"
  done < ci/oracle-binaries.lock
  ;;
 unit)
  exec bash tools/gate unit
  ;;
 build)
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  "$WOLF" build --deny-warnings src/vt/corpus_properties.lu -o "$root/target/native/corpus-properties"
  "$WOLF" build --deny-warnings src/vt/cursor_origin_rows.lu -o "$root/target/native/cursor-origin"
  printf 'PASS origin-build pinned-wolf deny-warnings\n'
  ;;
 native)
  "$root/target/native/cursor-origin"
  printf 'PASS origin-cursor-native defaults zero clamp CUF CUB print origin-off 1049 in-region\n'
  ;;
 checked)
  . tools/toolchain-env.sh
  "$WOLF" conform-run src/vt/cursor_origin_rows.lu --json --checked --deny-warnings > target/gate/origin.checked.json
  python3 -I - <<'PY'
from pathlib import Path
import json,sys,tomllib
root=Path.cwd()
sys.path.insert(0,str(root/'tests/vt'))
from checked_rows import validate
validate(json.loads((root/'target/gate/origin.checked.json').read_text()),tomllib.loads((root/'wolf-toolchain.toml').read_text())['wolf'])
print('PASS origin-cursor-explicit-checked no-native-fallback')
PY
  ;;
 lupin)
  . tools/toolchain-env.sh
  "$LUPIN" run src/vt/cursor_origin_rows.lu
  printf 'PASS origin-cursor-lupin\n'
  ;;
 oracle)
  . tools/toolchain-env.sh
  python3 -I tests/vt/origin_horizontal_rows.py "$root/target/native/warren"
  python3 -I tests/vt/origin_horizontal_rows.py "$LUPIN" run src/warren.lu
  ;;
 frozen)
  for script in compare_cases compare_combining compare_combine_anchor compare_erase_reflow compare_annotations compare_erase_extents compare_probes compare_checkpoints; do
    python3 -I "tests/vt/$script.py" "$root/target/native/warren"
  done
  for suite in census recordings fuzz-baseline; do
    python3 -I tests/vt/compare_suite.py --suite "$suite" "$root/target/native/warren"
  done
  python3 -I tests/vt/compare_d9.py "$root/target/native/warren"
  python3 -I tests/vt/chunking_suite.py "$root/target/native/warren"
  python3 -I tests/vt/corpus_properties.py "$root/target/native/corpus-properties" "$root/target/native/warren"
  ;;
 fresh)
  python3 -I tests/vt/fresh_fuzz.py --profile pull-request --out target/origin-pr-fresh "$root/target/native/warren" "$root/target/native/corpus-properties"
  ;;
 known)
  mapfile -t seeds < <(python3 -I - <<'PY'
import json
known=json.load(open('tests/vt/fresh-known.json'))
fixed=json.load(open('tests/vt/origin-horizontal-seeds.json'))
assert len(fixed)==13 and len(set(fixed))==13
assert not set(fixed).intersection(known)
assert all(row['issue']!=32 for row in known.values())
print(*sorted(set(known).union(fixed)),sep='\n')
PY
)
  [ "${#seeds[@]}" -gt 13 ]
  args=()
  for seed in "${seeds[@]}"; do args+=(--case "$seed"); done
  python3 -I tests/vt/fresh_fuzz.py --profile nightly "${args[@]}" --out target/origin-known-cases "$root/target/native/warren" "$root/target/native/corpus-properties"
  python3 -I - <<'PY'
import json
known=json.load(open('tests/vt/fresh-known.json'))
fixed=json.load(open('tests/vt/origin-horizontal-seeds.json'))
result=json.load(open('target/origin-known-cases/result.json'))
assert set(result['known'])==set(known)
assert not result['failed'] and not result['fixed']
assert all(not result['cases'][seed]['failures'] for seed in fixed)
print('PASS origin-known-exact removed=%d remaining=%d no-other-change' % (len(fixed),len(known)))
PY
  ;;
 plant)
  . tools/toolchain-env.sh
  exec python3 -I tests/vt/origin_horizontal_rows.py "$LUPIN" run src/warren.lu
  ;;
 *) printf 'FAIL origin-rig unknown-step\n'; exit 2 ;;
esac
