#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
DEMO_DIR="$ROOT_DIR/examples/agent_capsule_demo/handoff"
POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-strict.json"
TMP_DIR=$(mktemp -d)
CAPSULE="$TMP_DIR/capsule.txt"
OUT_DIR="$TMP_DIR/decoded"
NGRAM_PAYLOAD="$TMP_DIR/ngram-payload.txt"
NGRAM_CAPSULE="$TMP_DIR/ngram-capsule.txt"
NGRAM_OUT="$TMP_DIR/ngram-decoded"
SIGNED_PAYLOAD="$TMP_DIR/signed-payload.txt"
SIGNED_CAPSULE="$TMP_DIR/signed-capsule.txt"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m agentcapsule.cli pack "$DEMO_DIR" --out "$CAPSULE"
"$PYTHON" -m agentcapsule.cli inspect "$CAPSULE"
"$PYTHON" -m agentcapsule.cli verify "$CAPSULE" --policy "$POLICY"
"$PYTHON" -m agentcapsule.cli unpack "$CAPSULE" --out "$OUT_DIR" --policy "$POLICY"
"$PYTHON" -m agentcapsule.cli codecs
"$PYTHON" -m agentcapsule.cli scan "$CAPSULE" --json >/dev/null

printf 'ngram capsule demo\n' > "$NGRAM_PAYLOAD"
"$PYTHON" -m agentcapsule.cli pack "$NGRAM_PAYLOAD" \
  --codec lmcodec-ngram-v2 \
  --model "$ROOT_DIR/tests/fixtures/ngram_model_v1.json" \
  --out "$NGRAM_CAPSULE"
"$PYTHON" -m agentcapsule.cli verify "$NGRAM_CAPSULE"
"$PYTHON" -m agentcapsule.cli unpack "$NGRAM_CAPSULE" --out "$NGRAM_OUT"

printf 'signed capsule demo\n' > "$SIGNED_PAYLOAD"
CAPSULE_HMAC_KEY='demo shared secret' "$PYTHON" -m agentcapsule.cli pack "$SIGNED_PAYLOAD" \
  --out "$SIGNED_CAPSULE" \
  --sign-key-env CAPSULE_HMAC_KEY \
  --signature-key-id demo
CAPSULE_HMAC_KEY='demo shared secret' "$PYTHON" -m agentcapsule.cli verify "$SIGNED_CAPSULE" --key-env CAPSULE_HMAC_KEY

cmp "$DEMO_DIR/notes.md" "$OUT_DIR/notes.md"
cmp "$DEMO_DIR/manifest-example.json" "$OUT_DIR/manifest-example.json"
cmp "$DEMO_DIR/tool-config.json" "$OUT_DIR/tool-config.json"
cmp "$NGRAM_PAYLOAD" "$NGRAM_OUT/ngram-payload.txt"

echo "Agent Capsule demo ok"
