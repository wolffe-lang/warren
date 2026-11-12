#!/usr/bin/env bash
set -euo pipefail
exec "${WARREN_ENGINE:-podman}" "$@"
