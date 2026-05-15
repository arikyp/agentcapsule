#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="${TMPDIR:-/tmp}"
PAYLOAD="$TMP/lmcodec-compare-payload.bin"
FIXED_MESSAGE="$TMP/lmcodec-fixed-message.txt"
FIXED_OUTPUT="$TMP/lmcodec-fixed-output.bin"
NGRAM_MODEL="$TMP/lmcodec-ngram-model.json"
NGRAM_MESSAGE="$TMP/lmcodec-ngram-message.txt"
NGRAM_OUTPUT="$TMP/lmcodec-ngram-output.bin"

python3 - "$PAYLOAD" <<'PY'
from pathlib import Path
import sys

payload = (
    b"LMCodec demo payload\n"
    + bytes(range(64))
    + b"\nThis binary blob should roundtrip exactly.\n"
)
Path(sys.argv[1]).write_bytes(payload)
PY

echo "[fixed carrier]"
PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli encode --in "$PAYLOAD" --out "$FIXED_MESSAGE" --wrap 80
PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli decode --in "$FIXED_MESSAGE" --out "$FIXED_OUTPUT"
cmp "$PAYLOAD" "$FIXED_OUTPUT"

echo
echo "[order-1 ngram carrier]"
PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli train \
  --data "$ROOT/examples/carrier_corpus_v1.txt" \
  --out "$NGRAM_MODEL" \
  --order 1 \
  --uniform-mix 0.75
PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli encode --model "$NGRAM_MODEL" --in "$PAYLOAD" --out "$NGRAM_MESSAGE" --wrap 80
PYTHONPATH="$ROOT/src" python3 -m lmcodec.cli decode --model "$NGRAM_MODEL" --in "$NGRAM_MESSAGE" --out "$NGRAM_OUTPUT"
cmp "$PAYLOAD" "$NGRAM_OUTPUT"

echo
echo "fixed message: $FIXED_MESSAGE"
echo "ngram message: $NGRAM_MESSAGE"
echo "comparison roundtrip ok"

