#!/usr/bin/env bash
# Read-only image validation. No compiler, oracle replay or heavy lock.
set -euo pipefail
root=$PWD
engine=${WARREN_ENGINE:?set WARREN_ENGINE to an absolute executable path}
case "$engine" in /*) ;; *) printf 'REFUSED engine-path-not-absolute\n'; exit 75 ;; esac
[ -x "$engine" ] || { printf 'REFUSED engine-not-executable\n'; exit 75; }
wrapper="$root/tests/proto/rig/engine.sh"
[ -x "$wrapper" ] || { printf 'REFUSED wrapper-not-executable\n'; exit 75; }
mkdir -p target/proto/preflight target/tmp
export TMPDIR="$root/target/tmp"
image=localhost/wr02-oracle:1
"$wrapper" image inspect --format '{{.Id}}' "$image" > target/proto/preflight/image-id.txt
for file in oracle-packages.txt oracle-binaries.txt; do
  "$wrapper" run --rm --network=none --memory=256m "$image" \
    sh -c 'cat "$1"' sh "/opt/$file" > "target/proto/preflight/$file"
done
diff -u ci/packages.txt target/proto/preflight/oracle-packages.txt
diff -u ci/oracle-binaries.lock target/proto/preflight/oracle-binaries.txt
printf 'PASS preflight-only engine-absolute wrapper-absolute image-package-and-binary-pins\n'
