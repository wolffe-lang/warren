# Sourced, never run: WOLF, LUPIN, WOLF_STD and LUPIN_STD from the staged pin.
# PATH is not consulted; a wolf on PATH is whatever the machine last installed.
stage=${WARREN_TOOLCHAIN_DIR:-$root/.wolf-bin}
[ -f "$stage/manifest.json" ] || { echo 'FAIL toolchain: run tools/fetch-toolchain.py first'; exit 1; }
WOLF=$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["tools"]["wolf"]["root"]+"/wolf")' "$stage/manifest.json")
LUPIN=$(python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["tools"]["lupin"]["root"]+"/lupin")' "$stage/manifest.json")
WOLF_STD=$stage/std
LUPIN_STD=$stage/std
want=$(python3 -I -c 'import sys,tomllib; print(tomllib.load(open(sys.argv[1],"rb"))["std"]["rev"])' "$root/wolf-toolchain.toml")
[ "$(cat "$WOLF_STD/STD-REV" 2>/dev/null)" = "$want" ] || { echo 'FAIL toolchain: staged std is not the pin'; exit 1; }
export WOLF LUPIN WOLF_STD LUPIN_STD
