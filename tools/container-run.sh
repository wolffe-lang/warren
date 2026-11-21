# Sourced by tools/in-container and tools/container-rows: how every warren
# container is started, so the rows that hold a container to its limits run
# under the very flags the gate runs under. Swap is bounded with memory: the
# hosted runner has no swap, so a limit on memory alone would let a local run
# on a machine with swap pass a step the runner kills.
# The command starts through a step that clears the signal mask, then through
# `env --default-signal`, which returns every signal to its default: an
# engine's init (podman's catatonit) hands its child TSTP, TTIN and TTOU
# blocked, and Python, which clears the mask, leaves PIPE and XFSZ ignored.
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
  "$engine" run --rm --init --memory "$memory" --memory-swap "$memory" --pids-limit 4096 \
    ${options[@]+"${options[@]}"} "$image" \
    python3 -I -c 'import os, signal, sys; signal.pthread_sigmask(signal.SIG_SETMASK, []); os.execvp("env", ["env", "--default-signal"] + sys.argv[1:])' \
    "$@"
}
