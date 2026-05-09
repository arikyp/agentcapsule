#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-require-ed25519.json"
TMP_DIR=$(mktemp -d)
PRIVATE_KEY="$TMP_DIR/publisher.key"
PUBLIC_KEY="$TMP_DIR/publisher.pub"
PAYLOAD="$TMP_DIR/payload.txt"
CAPSULE="$TMP_DIR/ed25519-capsule.txt"
REGISTRY_CAPSULE="$TMP_DIR/ed25519-registry-capsule.txt"
OUT_DIR="$TMP_DIR/decoded"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON" -c 'import cryptography' >/dev/null 2>&1; then
  echo "Ed25519 demo requires installing the optional signing extra: lmcodec[signing]"
  exit 0
fi

printf 'ed25519 signed capsule demo\n' > "$PAYLOAD"

"$PYTHON" -m agentcapsule.cli keys generate --private-key "$PRIVATE_KEY" --public-key "$PUBLIC_KEY"
"$PYTHON" -m agentcapsule.cli keys fingerprint --public-key "$PUBLIC_KEY"

"$PYTHON" -m agentcapsule.cli pack "$PAYLOAD" \
  --out "$CAPSULE" \
  --sign-ed25519-key "$PRIVATE_KEY" \
  --signature-key-id demo-ed25519
"$PYTHON" -m agentcapsule.cli inspect "$CAPSULE"
"$PYTHON" -m agentcapsule.cli verify "$CAPSULE" --policy "$POLICY"
"$PYTHON" -m agentcapsule.cli unpack "$CAPSULE" --out "$OUT_DIR" --policy "$POLICY"

"$PYTHON" -m agentcapsule.cli pack "$PAYLOAD" \
  --out "$REGISTRY_CAPSULE" \
  --sign-ed25519-key "$PRIVATE_KEY" \
  --signature-key-id demo-ed25519 \
  --no-inline-public-key
"$PYTHON" -m agentcapsule.cli verify "$REGISTRY_CAPSULE" \
  --policy "$POLICY" \
  --ed25519-public-key "$PUBLIC_KEY"

cmp "$PAYLOAD" "$OUT_DIR/payload.txt"

echo "Agent Capsule Ed25519 demo ok"
