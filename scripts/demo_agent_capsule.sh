#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
DEMO_DIR="$ROOT_DIR/examples/agent_capsule_demo/handoff"
POLICY="$ROOT_DIR/examples/agent_capsule_demo/policy-strict.json"
TMP_DIR=$(mktemp -d)
CAPSULE="$TMP_DIR/capsule.txt"
OUT_DIR="$TMP_DIR/decoded"

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

cmp "$DEMO_DIR/notes.md" "$OUT_DIR/notes.md"
cmp "$DEMO_DIR/manifest-example.json" "$OUT_DIR/manifest-example.json"
cmp "$DEMO_DIR/tool-config.json" "$OUT_DIR/tool-config.json"

echo "Agent Capsule demo ok"
