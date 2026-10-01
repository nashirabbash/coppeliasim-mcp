#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ ! -d "$DIR/.venv" ]; then
    python3 -m venv "$DIR/.venv"
fi
"$DIR/.venv/bin/pip" install --quiet --upgrade pip pyzmq cbor2 pillow
echo "Environment setup complete in $DIR/.venv"
