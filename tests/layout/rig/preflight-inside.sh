#!/usr/bin/env bash
# Read-only checks inside the pinned oracle image, before the first step:
# its package list and reference binaries, the tool pins, and the CPUs the
# take was given (WARREN_CPUS, as taskset spells them).
set -euo pipefail
root=$PWD
diff -u ci/packages.txt /opt/oracle-packages.txt
diff -u ci/oracle-binaries.lock /opt/oracle-binaries.txt
python3 -I - "${WARREN_CPUS:?set WARREN_CPUS}" <<'PY'
from pathlib import Path
import hashlib, os, shutil, sys, tomllib
want = set()
for part in sys.argv[1].split(','):
    lo, _, hi = part.partition('-')
    want.update(range(int(lo), int(hi or lo) + 1))
assert os.sched_getaffinity(0) == want, (os.sched_getaffinity(0), want)
pins = tomllib.loads(Path('warren-oracle.toml').read_text())
for name in ('xterm', 'tmux', 'Xvfb', 'infocmp'):
    digest = hashlib.sha256(Path(shutil.which(name)).read_bytes()).hexdigest()
    assert digest == pins[name.lower()]['sha256'], name
print('PASS layout-preflight cpus=%s reference-binaries' % sys.argv[1])
PY
python3 -I tools/check-pins.py
. tools/toolchain-env.sh
"$WOLF" --version | head -n 1
"$LUPIN" --version | head -n 1
printf 'PASS layout-preflight-inside packages binaries pins\n'
