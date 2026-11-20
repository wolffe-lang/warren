#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, inside the pinned oracle image,
# from a committed checkout with the pinned toolchain staged in .wolf-bin.
#   gate-linux  the whole Linux gate (it runs the D15 rows, the frozen D15
#               observations and warren's frames for them)
#   seeds       under the nightly profile: the seeds of dch-tail-seeds.json pass,
#               each with a D15 permitted delta, and the known list is empty
#   build       warren and the properties program the plant's row needs
#   plant       the same seeds, which a plant must turn red: it prints
#               FAIL dch-tail-seeds-pass and ends 1
set -euo pipefail
root=$PWD
export HOME="$root/target/home" TMPDIR="$root/target/tmp" SHELL=/bin/sh LC_ALL=C.UTF-8 TZ=UTC
mkdir -p "$HOME" "$TMPDIR" target/native
build() {
  . tools/toolchain-env.sh
  python3 -I tools/vt/generate_version.py
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/dch-warren"
  "$WOLF" build --deny-warnings src/vt/corpus_properties.lu -o "$root/target/native/dch-properties"
}
drive() {
  rm -rf target/dch-tail-seeds
  mapfile -t seeds < <(python3 -I -c 'import json; print(*json.load(open("tests/vt/dch-tail-seeds.json")), sep="\n")')
  [ "${#seeds[@]}" -eq 2 ]
  args=()
  for seed in "${seeds[@]}"; do args+=(--case "$seed"); done
  python3 -I tests/vt/fresh_fuzz.py --profile nightly "${args[@]}" --out target/dch-tail-seeds \
    "$root/target/native/dch-warren" "$root/target/native/dch-properties" || true
  python3 -I - <<'PY'
import json
seeds = json.load(open('tests/vt/dch-tail-seeds.json'))
known = json.load(open('tests/vt/fresh-known.json'))
result = json.load(open('target/dch-tail-seeds/result.json'))
problems = []
if known:
    problems.append('known list not empty: %s' % sorted(known))
if result['failed'] or result['known'] or result['fixed']:
    problems.append('failed=%s known=%s fixed=%s' % (result['failed'], result['known'], result['fixed']))
for seed in seeds:
    entry = result['cases'][seed]
    cells = (entry['rules'].get('D15') or {}).get('cells', [])
    if entry['failures'] or not cells:
        problems.append('%s failures=%s d15-cells=%d' % (
            seed, ','.join(f['name'] for f in entry['failures']) or '-', len(cells)))
if problems:
    print('FAIL dch-tail-seeds-pass ' + '; '.join(problems))
    raise SystemExit(1)
print('PASS dch-tail-seeds-pass seeds=%d each-with-a-D15-cell known=0' % len(seeds))
PY
}
case "${1:-}" in
 gate-linux)
  exec bash tools/gate linux
  ;;
 seeds)
  build
  drive
  ;;
 build)
  build
  ;;
 plant)
  drive
  ;;
 *) printf 'FAIL dch-tail-rig unknown-step\n'; exit 2 ;;
esac
