#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, inside the pinned oracle image,
# from a committed checkout with the pinned toolchain staged in .wolf-bin.
#   gate-linux  the whole Linux gate (it runs the wide-scalar rows natively,
#               on the checked machine, under lupin and live against the
#               reference)
#   known       under the nightly profile: the seeds of wide-pending-seeds.json
#               pass, and every seed the known list keeps fails exactly as listed
#   build       the native binary the plant's row needs
#   plant       the live wide-scalar rows natively, which a plant must turn red
#               at wide-pending-off-wide-pending-wide; the recorder checks its
#               FAIL line
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
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren"
  ;;
 plant)
  exec python3 -I tests/vt/wide_pending_rows.py --out "$root/target/wide-pending-plant" "$root/target/native/warren"
  ;;
 known)
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/wide-warren"
  "$WOLF" build --deny-warnings src/vt/corpus_properties.lu -o "$root/target/native/wide-properties"
  mapfile -t seeds < <(python3 -I - <<'PY'
import json
known = json.load(open('tests/vt/fresh-known.json'))
fixed = json.load(open('tests/vt/wide-pending-seeds.json'))
assert len(fixed) == 21 and len(set(fixed)) == 21
assert not set(fixed) & set(known)
assert all(row['issue'] != 28 for row in known.values())
print(*sorted(set(known) | set(fixed)), sep='\n')
PY
)
  [ "${#seeds[@]}" -gt 21 ]
  args=()
  for seed in "${seeds[@]}"; do args+=(--case "$seed"); done
  rm -rf target/wide-known-cases
  python3 -I tests/vt/fresh_fuzz.py --profile nightly "${args[@]}" --out target/wide-known-cases \
    "$root/target/native/wide-warren" "$root/target/native/wide-properties"
  python3 -I - <<'PY'
import json
known = json.load(open('tests/vt/fresh-known.json'))
fixed = json.load(open('tests/vt/wide-pending-seeds.json'))
result = json.load(open('target/wide-known-cases/result.json'))
assert set(result['known']) == set(known), sorted(result['known'])
assert not result['failed'] and not result['fixed'], (result['failed'], result['fixed'])
assert all(not result['cases'][seed]['failures'] for seed in fixed)
print('PASS wide-known-exact passed=%d known=%d nothing-else' % (len(fixed), len(known)))
PY
  ;;
 *) printf 'FAIL wide-pending-rig unknown-step\n'; exit 2 ;;
esac
