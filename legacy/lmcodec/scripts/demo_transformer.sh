#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="${TMPDIR:-/tmp}"
PAYLOAD="$TMP/lmcodec-transformer-payload.bin"
MESSAGE="$TMP/lmcodec-transformer-message.txt"
OUTPUT="$TMP/lmcodec-transformer-output.bin"
MODEL="$ROOT/tests/fixtures/transformer_model_v1.json"

python3 - "$PAYLOAD" <<'PY'
from pathlib import Path
import sys

Path(sys.argv[1]).write_bytes(bytes(range(256)))
PY

PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli encode \
  --model "$MODEL" \
  --in "$PAYLOAD" \
  --out "$MESSAGE" \
  --wrap 80 \
  --shape-uniform-mix 0.80 \
  --temperature 1.25 \
  --max-steps 100000

PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli decode \
  --model "$MODEL" \
  --in "$MESSAGE" \
  --out "$OUTPUT"

cmp "$PAYLOAD" "$OUTPUT"
echo "transformer roundtrip ok: $MESSAGE"
