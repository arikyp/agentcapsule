#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
GOV_DIR="$ROOT_DIR/examples/agent_capsule_demo/governance"
OBSERVE_POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-observe.json"
SIGNED_POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-require-hmac.json"
TMP_DIR=$(mktemp -d)
UNSIGNED_CAPSULE="$TMP_DIR/unsigned-capsule.txt"
SIGNED_CAPSULE="$TMP_DIR/signed-capsule.txt"
TAMPERED_CAPSULE="$TMP_DIR/tampered-capsule.txt"

cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

export PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR/legacy/lmcodec/src${PYTHONPATH:+:$PYTHONPATH}"

"$PYTHON" -m agentcapsule.cli pack "$GOV_DIR/unsigned-note.txt" --out "$UNSIGNED_CAPSULE"
"$PYTHON" -m agentcapsule.cli scan "$UNSIGNED_CAPSULE" --policy "$OBSERVE_POLICY"

if "$PYTHON" -m agentcapsule.cli verify "$UNSIGNED_CAPSULE" --policy "$SIGNED_POLICY"; then
  echo "strict policy unexpectedly accepted unsigned capsule" >&2
  exit 1
fi

CAPSULE_HMAC_KEY='demo shared secret' "$PYTHON" -m agentcapsule.cli pack "$GOV_DIR/signed-note.txt" \
  --out "$SIGNED_CAPSULE" \
  --sign-key-env CAPSULE_HMAC_KEY \
  --signature-key-id demo-governance
CAPSULE_HMAC_KEY='demo shared secret' "$PYTHON" -m agentcapsule.cli verify "$SIGNED_CAPSULE" \
  --policy "$SIGNED_POLICY" \
  --key-env CAPSULE_HMAC_KEY
"$PYTHON" -m agentcapsule.cli scan "$SIGNED_CAPSULE" --policy "$SIGNED_POLICY" --json >/dev/null

cp "$SIGNED_CAPSULE" "$TAMPERED_CAPSULE"
"$PYTHON" - "$TAMPERED_CAPSULE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "-----PAYLOAD-----\n"
before, payload = text.split(marker, 1)
chars = list(payload)
for index, char in enumerate(chars):
    if char.isalnum():
        chars[index] = "A" if char != "A" else "B"
        break
path.write_text(before + marker + "".join(chars), encoding="utf-8", newline="\n")
PY

if CAPSULE_HMAC_KEY='demo shared secret' "$PYTHON" -m agentcapsule.cli verify "$TAMPERED_CAPSULE" \
  --policy "$SIGNED_POLICY" \
  --key-env CAPSULE_HMAC_KEY; then
  echo "tampered capsule unexpectedly verified" >&2
  exit 1
fi
"$PYTHON" -m agentcapsule.cli scan "$TAMPERED_CAPSULE" --policy "$SIGNED_POLICY"

echo "Agent Capsule governance demo ok"
