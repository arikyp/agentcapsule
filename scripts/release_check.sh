#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="${TMPDIR:-/tmp}/agentcapsule-release-check"
VENV="$TMP/venv"
PAYLOAD="$TMP/payload.bin"
MESSAGE="$TMP/message.txt"
OUTPUT="$TMP/output.bin"
TRANSFORMER_MESSAGE="$TMP/transformer-message.txt"
TRANSFORMER_OUTPUT="$TMP/transformer-output.bin"

rm -rf "$TMP"
mkdir -p "$TMP"

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -e "$ROOT"

"$VENV/bin/python" - "$PAYLOAD" <<'PY'
from pathlib import Path
import sys
Path(sys.argv[1]).write_bytes(bytes(range(256)))
PY

"$VENV/bin/python" -m lmcodec.cli encode --in "$PAYLOAD" --out "$MESSAGE" --wrap 80
"$VENV/bin/python" -m lmcodec.cli decode --in "$MESSAGE" --out "$OUTPUT"
cmp "$PAYLOAD" "$OUTPUT"

"$VENV/bin/python" -m lmcodec.cli encode \
  --model "$ROOT/tests/fixtures/transformer_model_v1.json" \
  --in "$PAYLOAD" \
  --out "$TRANSFORMER_MESSAGE" \
  --wrap 80 \
  --shape-uniform-mix 0.80 \
  --temperature 1.25 \
  --max-steps 100000
"$VENV/bin/python" -m lmcodec.cli decode \
  --model "$ROOT/tests/fixtures/transformer_model_v1.json" \
  --in "$TRANSFORMER_MESSAGE" \
  --out "$TRANSFORMER_OUTPUT"
cmp "$PAYLOAD" "$TRANSFORMER_OUTPUT"

sh "$ROOT/scripts/verify_v1.sh"

echo "Agent Capsule release check ok"
