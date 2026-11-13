#!/usr/bin/env bash
# Standalone read-only preparation: no compiler, replay, fuzz or heavy lock.
set -euo pipefail
root=$PWD
engine=${WARREN_ENGINE:?set WARREN_ENGINE to an absolute executable path}
case "$engine" in /*) ;; *) printf 'REFUSED engine-path-not-absolute\n'; exit 75 ;; esac
[ -x "$engine" ] || { printf 'REFUSED engine-not-executable\n'; exit 75; }
wrapper="$root/tests/vt/rig/engine.sh"
[ -x "$wrapper" ] || { printf 'REFUSED wrapper-not-executable\n'; exit 75; }
image=${WARREN_ORACLE_IMAGE:-localhost/wr01-grid-oracle:1}
out="$root/target/vt/preflight"
mkdir -p "$out" "$root/target/tmp"
export TMPDIR="$root/target/tmp"
"$wrapper" image inspect --format '{{.Id}}' "$image" > "$out/image-id.txt"
for file in oracle-packages.txt oracle-binaries.txt; do
  "$wrapper" run --rm --network=none --read-only --memory=256m "$image" \
    sh -c 'cat "$1"' sh "/opt/$file" > "$out/$file"
done
diff -u ci/packages.txt "$out/oracle-packages.txt"
diff -u ci/oracle-binaries.lock "$out/oracle-binaries.txt"
"$wrapper" run --rm --network=none --read-only --memory=256m "$image" sh -c '
for tool in xterm tmux Xvfb infocmp; do
  printf "%s " "$tool"
  sha256sum "$(command -v "$tool")"
done' > "$out/binaries.actual"
python3 -I - "$root" "$out" <<'PY'
from pathlib import Path
import sys
import tomllib
root, out = map(Path, sys.argv[1:])
pins = tomllib.loads((root / 'warren-oracle.toml').read_text())
actual = {}
for line in (out / 'binaries.actual').read_text().splitlines():
    name, digest, path = line.split()
    actual[name.lower()] = digest
for name in ('xterm', 'tmux', 'xvfb', 'infocmp'):
    assert actual[name] == pins[name]['sha256'], name
print('PASS vt-preflight actual-binary-digests')
PY
"$wrapper" run --rm --network=none --read-only --memory=256m \
  -v "$root:$root:ro" -w "$root" "$image" \
  python3 -I tests/vt/rig/unicode_identity.py > "$out/libc-unicode.json"
printf 'PASS vt-preflight-only engine-absolute image-packages actual-binaries locale-identity\n'
