#!/usr/bin/env bash
# Convenience wrapper to launch the SP1 MAS via the CLI.
set -euo pipefail

cd "$(dirname "$0")/../../.." || exit 1

# Default .env loading
if [ -f src/sp1/.env ]; then
    export $(grep -v '^#' src/sp1/.env | xargs)
fi

PYTHONPATH=src uv run python -m sp1.cli run "$@"
