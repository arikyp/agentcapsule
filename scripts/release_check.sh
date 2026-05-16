#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
TMP="${TMPDIR:-/tmp}/agentcapsule-release-check"
VENV="$TMP/venv"
PAYLOAD="$TMP/payload.txt"
CAPSULE="$TMP/payload.capsule.txt"
OUT_DIR="$TMP/unpacked"
ZSTD_CAPSULE="$TMP/payload.zstd.capsule.txt"
ZSTD_OUT_DIR="$TMP/unpacked-zstd"
ENC_CAPSULE="$TMP/payload.encrypted.capsule.txt"
ENC_OUT_DIR="$TMP/unpacked-encrypted"
STRICT_BLOCK_THREAD="$TMP/strict-block-thread.txt"
STRICT_OUT_DIR="$TMP/strict-output"
FETCH_OUT="$TMP/fetch-output.capsule.txt"

rm -rf "$TMP"
mkdir -p "$TMP"

python3 -m venv "$VENV"
"$VENV/bin/python" -m pip install -e "$ROOT[all]"

printf 'agent capsule release check\n' > "$PAYLOAD"
"$VENV/bin/agentcapsule" pack "$PAYLOAD" --out "$CAPSULE"
"$VENV/bin/agentcapsule" verify "$CAPSULE"
"$VENV/bin/agentcapsule" unpack "$CAPSULE" --out "$OUT_DIR"
cmp "$PAYLOAD" "$OUT_DIR/payload.txt"

("$VENV/bin/agentcapsule" pack "$PAYLOAD" --out "$ZSTD_CAPSULE" --compression zstd)
("$VENV/bin/agentcapsule" verify "$ZSTD_CAPSULE")
("$VENV/bin/agentcapsule" unpack "$ZSTD_CAPSULE" --out "$ZSTD_OUT_DIR")
cmp "$PAYLOAD" "$ZSTD_OUT_DIR/payload.txt"

export CAPSULE_ENCRYPTION_KEY_B64='a2tra2tra2tra2tra2tra2tra2tra2tra2tra2tra2s='
"$VENV/bin/agentcapsule" pack "$PAYLOAD" --out "$ENC_CAPSULE" --encrypt aes-256-gcm --encryption-key-env CAPSULE_ENCRYPTION_KEY_B64
"$VENV/bin/agentcapsule" verify "$ENC_CAPSULE" --encryption-key-env CAPSULE_ENCRYPTION_KEY_B64
"$VENV/bin/agentcapsule" unpack "$ENC_CAPSULE" --out "$ENC_OUT_DIR" --encryption-key-env CAPSULE_ENCRYPTION_KEY_B64
cmp "$PAYLOAD" "$ENC_OUT_DIR/payload.txt"

printf 'safe\342\200\213text\n' > "$STRICT_BLOCK_THREAD"
if "$VENV/bin/agentcapsule" ingest "$STRICT_BLOCK_THREAD" --out "$STRICT_OUT_DIR" --strict --json >/dev/null 2>&1; then
  echo "strict ingest expected non-zero on block disposition" >&2
  exit 1
fi

if "$VENV/bin/agentcapsule" fetch --uri file:///tmp/capsule.txt --out "$FETCH_OUT" >/dev/null 2>&1; then
  echo "fetch expected to reject file:// URI scheme" >&2
  exit 1
fi

echo "Agent Capsule release check ok"
