#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, inside the pinned oracle image,
# from a committed checkout with the pinned toolchain staged in .wolf-bin.
#   gate-linux  the whole Linux gate (it runs the paint properties rows)
#   known       under the nightly profile: the seeds of paint-properties-seeds.json
#               pass, and every seed the known list keeps fails exactly as listed
#   build       the properties program the plant's row needs
#   plant       the paint properties rows, which a plant must turn red at
#               painted-row-below-cursor-4397; the recorder checks its FAIL line
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
  "$WOLF" build --deny-warnings src/vt/corpus_properties.lu -o "$root/target/native/corpus-properties"
  ;;
 plant)
  exec python3 -I tests/vt/paint_properties_rows.py "$root/target/native/corpus-properties"
  ;;
 known)
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/paint-warren"
  "$WOLF" build --deny-warnings src/vt/corpus_properties.lu -o "$root/target/native/paint-properties"
  mapfile -t seeds < <(python3 -I - <<'PY'
import json
known = json.load(open('tests/vt/fresh-known.json'))
fixed = json.load(open('tests/vt/paint-properties-seeds.json'))
assert len(fixed) == 5 and len(set(fixed)) == 5
assert not set(fixed) & set(known)
assert all(row['issue'] != 31 for row in known.values())
print(*sorted(set(known) | set(fixed)), sep='\n')
PY
)
  [ "${#seeds[@]}" -gt 5 ]
  args=()
  for seed in "${seeds[@]}"; do args+=(--case "$seed"); done
  rm -rf target/paint-known-cases
  python3 -I tests/vt/fresh_fuzz.py --profile nightly "${args[@]}" --out target/paint-known-cases \
    "$root/target/native/paint-warren" "$root/target/native/paint-properties"
  python3 -I - <<'PY'
import json
known = json.load(open('tests/vt/fresh-known.json'))
fixed = json.load(open('tests/vt/paint-properties-seeds.json'))
result = json.load(open('target/paint-known-cases/result.json'))
assert set(result['known']) == set(known), sorted(result['known'])
assert not result['failed'] and not result['fixed'], (result['failed'], result['fixed'])
assert all(not result['cases'][seed]['failures'] for seed in fixed)
print('PASS paint-known-exact passed=%d known=%d nothing-else' % (len(fixed), len(known)))
PY
  ;;
 *) printf 'FAIL paint-properties-rig unknown-step\n'; exit 2 ;;
esac
