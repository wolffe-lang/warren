# Sourced by tools/in-container and tools/container-rows: how every warren
# container is started, so the rows that hold a container to its limits run
# under the very flags the gate runs under.
#   container_run ENGINE MEMORY IMAGE [RUN-OPTION ...] -- COMMAND [ARG ...]
container_run() {
  local engine=$1 memory=$2 image=$3
  shift 3
  local options=()
  while [ "$#" -gt 0 ] && [ "$1" != -- ]; do
    options+=("$1")
    shift
  done
  [ "$#" -gt 0 ] && shift
  "$engine" run --rm --init --memory "$memory" --pids-limit 4096 \
    ${options[@]+"${options[@]}"} "$image" "$@"
}
