#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
TMP_DIR=$(mktemp -d)
ALLOW_PAYLOAD="$TMP_DIR/allow.txt"
ALLOW_CAPSULE="$TMP_DIR/allow-capsule.txt"
REVIEW_TEXT="$TMP_DIR/review.txt"
BLOCK_TEXT="$TMP_DIR/block.txt"
REGISTRY="$TMP_DIR/registry.json"
SIGNED_PAYLOAD="$TMP_DIR/signed.txt"
SIGNED_CAPSULE="$TMP_DIR/signed-capsule.txt"
POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-require-ed25519-registry.json"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

pretty() {
  "$PYTHON" -m json.tool
}

printf 'audit allow payload\n' > "$ALLOW_PAYLOAD"
"$PYTHON" -m agentcapsule.cli pack "$ALLOW_PAYLOAD" --out "$ALLOW_CAPSULE" >/dev/null
echo "=== allow: verified capsule ==="
"$PYTHON" -m agentcapsule.cli verify "$ALLOW_CAPSULE" --audit-json | pretty

printf 'prefix\n%s\n' 'AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA' > "$REVIEW_TEXT"
echo "=== review: dense text scan ==="
"$PYTHON" -m agentcapsule.cli scan "$REVIEW_TEXT" --audit-json | pretty

printf '%s\n' 'not a capsule' > "$BLOCK_TEXT"
echo "=== block: invalid capsule ==="
"$PYTHON" -m agentcapsule.cli verify "$BLOCK_TEXT" --audit-json | pretty

if ! "$PYTHON" -c 'import cryptography' >/dev/null 2>&1; then
  echo "=== trusted signature: skipped, install optional signing extra ==="
  echo 'Run: python3 -m pip install -e ".[signing]"'
  exit 0
fi

"$PYTHON" -m agentcapsule.cli keys generate \
  --private-key "$TMP_DIR/publisher.key" \
  --public-key "$TMP_DIR/publisher.pub" >/dev/null
"$PYTHON" -m agentcapsule.cli keys registry-entry \
  --key-id publisher-prod \
  --public-key "$TMP_DIR/publisher.pub" \
  --publisher "Demo Publisher" > "$REGISTRY"
printf 'audit trusted signed payload\n' > "$SIGNED_PAYLOAD"
"$PYTHON" -m agentcapsule.cli pack "$SIGNED_PAYLOAD" \
  --out "$SIGNED_CAPSULE" \
  --sign-ed25519-key "$TMP_DIR/publisher.key" \
  --signature-key-id publisher-prod \
  --no-inline-public-key >/dev/null

echo "=== allow: registry-trusted signature ==="
"$PYTHON" -m agentcapsule.cli verify "$SIGNED_CAPSULE" \
  --policy "$POLICY" \
  --signature-registry "$REGISTRY" \
  --audit-json | pretty

echo "Agent Capsule audit demo ok"
