#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="${TMPDIR:-/tmp}/agentcapsule-release-check"
VENV="$TMP/venv"
PAYLOAD="$TMP/payload.txt"
CAPSULE="$TMP/payload.capsule.txt"
OUT_DIR="$TMP/unpacked"

rm -rf "$TMP"
mkdir -p "$TMP"

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -e "$ROOT"

printf 'agent capsule release check\n' > "$PAYLOAD"
"$VENV/bin/agentcapsule" pack "$PAYLOAD" --out "$CAPSULE"
"$VENV/bin/agentcapsule" verify "$CAPSULE"
"$VENV/bin/agentcapsule" unpack "$CAPSULE" --out "$OUT_DIR"
cmp "$PAYLOAD" "$OUT_DIR/payload.txt"

echo "Agent Capsule release check ok"
