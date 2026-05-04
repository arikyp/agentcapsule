#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PAYLOAD="${TMPDIR:-/tmp}/lmcodec-demo-payload.bin"
MESSAGE="${TMPDIR:-/tmp}/lmcodec-demo-message.txt"
OUTPUT="${TMPDIR:-/tmp}/lmcodec-demo-output.bin"

python3 - "$PAYLOAD" <<'PY'
from pathlib import Path
import sys

Path(sys.argv[1]).write_bytes(bytes(range(256)))
PY

PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli encode --in "$PAYLOAD" --out "$MESSAGE" --wrap 80
PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli decode --in "$MESSAGE" --out "$OUTPUT"

cmp "$PAYLOAD" "$OUTPUT"
echo "roundtrip ok: $MESSAGE"

