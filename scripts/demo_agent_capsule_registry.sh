#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-require-ed25519-registry.json"
TMP_DIR=$(mktemp -d)
REGISTRY="$TMP_DIR/registry.json"
PAYLOAD="$TMP_DIR/payload.txt"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

export PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR/legacy/lmcodec/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON" -c 'import cryptography' >/dev/null 2>&1; then
  echo "Ed25519 registry demo requires installing the optional signing extra: agentcapsule[signing]"
  exit 0
fi

printf 'registry trusted capsule demo\n' > "$PAYLOAD"

"$PYTHON" -m agentcapsule.cli keys generate --private-key "$TMP_DIR/prod.key" --public-key "$TMP_DIR/prod.pub"
"$PYTHON" -m agentcapsule.cli keys generate --private-key "$TMP_DIR/rotated.key" --public-key "$TMP_DIR/rotated.pub"
"$PYTHON" -m agentcapsule.cli keys generate --private-key "$TMP_DIR/revoked.key" --public-key "$TMP_DIR/revoked.pub"
"$PYTHON" -m agentcapsule.cli keys generate --private-key "$TMP_DIR/untrusted.key" --public-key "$TMP_DIR/untrusted.pub"

"$PYTHON" - "$REGISTRY" "$TMP_DIR/prod.pub" "$TMP_DIR/rotated.pub" "$TMP_DIR/revoked.pub" <<'PY'
import json
import sys
from pathlib import Path

from agentcapsule.trust import registry_entry_from_public_key_file

registry, prod, rotated, revoked = map(Path, sys.argv[1:])
entries = [
    registry_entry_from_public_key_file(
        key_id="publisher-prod-2026q2",
        public_key_path=prod,
        publisher="Demo Publisher",
        note="current production key",
    ),
    registry_entry_from_public_key_file(
        key_id="publisher-prod-2026q3",
        public_key_path=rotated,
        publisher="Demo Publisher",
        note="rotated production key",
    ),
    registry_entry_from_public_key_file(
        key_id="publisher-prod-2026q1",
        public_key_path=revoked,
        publisher="Demo Publisher",
        status="revoked",
        note="revoked production key",
    ),
]
registry.write_text(json.dumps({"keys": entries}, sort_keys=True), encoding="utf-8")
PY

"$PYTHON" -m agentcapsule.cli pack "$PAYLOAD" \
  --out "$TMP_DIR/trusted-capsule.txt" \
  --sign-ed25519-key "$TMP_DIR/prod.key" \
  --signature-key-id publisher-prod-2026q2 \
  --no-inline-public-key
"$PYTHON" -m agentcapsule.cli verify "$TMP_DIR/trusted-capsule.txt" \
  --policy "$POLICY" \
  --signature-registry "$REGISTRY"

"$PYTHON" -m agentcapsule.cli pack "$PAYLOAD" \
  --out "$TMP_DIR/rotated-capsule.txt" \
  --sign-ed25519-key "$TMP_DIR/rotated.key" \
  --signature-key-id publisher-prod-2026q3 \
  --no-inline-public-key
"$PYTHON" -m agentcapsule.cli inspect "$TMP_DIR/rotated-capsule.txt" \
  --policy "$POLICY" \
  --signature-registry "$REGISTRY" \
  --json >/dev/null

"$PYTHON" -m agentcapsule.cli pack "$PAYLOAD" \
  --out "$TMP_DIR/revoked-capsule.txt" \
  --sign-ed25519-key "$TMP_DIR/revoked.key" \
  --signature-key-id publisher-prod-2026q1 \
  --no-inline-public-key
if "$PYTHON" -m agentcapsule.cli verify "$TMP_DIR/revoked-capsule.txt" \
  --policy "$POLICY" \
  --signature-registry "$REGISTRY"; then
  echo "revoked capsule unexpectedly verified" >&2
  exit 1
fi

"$PYTHON" -m agentcapsule.cli pack "$PAYLOAD" \
  --out "$TMP_DIR/untrusted-inline-capsule.txt" \
  --sign-ed25519-key "$TMP_DIR/untrusted.key" \
  --signature-key-id untrusted-demo
"$PYTHON" -m agentcapsule.cli scan "$TMP_DIR/untrusted-inline-capsule.txt" --json >/dev/null

echo "Agent Capsule Ed25519 registry demo ok"
