#!/usr/bin/env bash
# Run by gauntlet-record's copied-script mode, from the committed checkout.
set -euo pipefail
root=$PWD
. "$root/tools/toolchain-env.sh"
python3 -I tools/vt/generate_version.py
mkdir -p target/native target/vt
case "${1:-}" in
 gate)
  export WARREN_FUZZ_PROFILE=${WARREN_FUZZ_PROFILE:-pull-request}
  exec bash tools/gate linux
  ;;
 resource)
  cc -std=c11 -O2 -Wall -Wextra -Werror tools/vt/measure_child.c -o target/native/measure-child
  "$WOLF" build --deny-warnings src/vt_resource_bench.lu -o "$root/target/native/vt-resource-bench"
  exec "$root/target/native/measure-child" "$root/target/native/vt-resource-bench"
  ;;
 widths)
  "$WOLF" build --deny-warnings src/vt_width_vector.lu -o "$root/target/native/vt-width-vector"
  python3 -I tests/vt/width_vector_rows.py --out target/vt/canonical-native-widths.bin "$root/target/native/vt-width-vector"
  python3 -I tools/vt/width_sweep.py --out target/vt/canonical-assigned-widths --native-vector target/vt/canonical-native-widths.bin
  "$WOLF" build --deny-warnings src/warren.lu -o "$root/target/native/warren-width-columns"
  exec python3 -I tests/vt/probes/width_columns.py --out target/vt/canonical-width-columns --native-vector target/vt/canonical-native-widths.bin --warren "$root/target/native/warren-width-columns" --warren-head "$(git rev-parse HEAD)"
  ;;
 recordings)
  exec python3 -I tests/vt/compare_suite.py --suite recordings --observer-timeout 1800 "$LUPIN" run src/warren.lu
  ;;
 *) printf 'FAIL w1-rig unknown-step\n'; exit 2 ;;
esac
