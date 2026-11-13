#!/usr/bin/env bash
set -euo pipefail
case "${WARREN_ENGINE:-}" in
  /*) exec "$WARREN_ENGINE" "$@" ;;
  *) printf 'REFUSED engine-path-not-absolute\n' >&2; exit 75 ;;
esac
