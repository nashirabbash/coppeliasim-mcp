#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$DIR/.." && pwd)"
"$REPO_DIR/.venv/bin/python" "$DIR/benchmark.py" "$@"
