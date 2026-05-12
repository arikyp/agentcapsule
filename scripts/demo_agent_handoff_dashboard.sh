#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
OUT_DIR=${OUT_DIR:-$(mktemp -d)}

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON" -c 'import cryptography' >/dev/null 2>&1; then
  echo "Agent handoff dashboard demo requires the optional signing extra for Ed25519."
  echo 'Run: python3 -m pip install -e ".[signing]"'
  exit 0
fi

"$PYTHON" "$ROOT_DIR/scripts/run_agent_handoff_policy_matrix.py" --out-dir "$OUT_DIR" --pretty >/dev/null
"$PYTHON" "$ROOT_DIR/scripts/evaluate_agent_handoff_transcript.py" \
  --events "$OUT_DIR/events.jsonl" \
  --message "$OUT_DIR/agent-a-to-agent-b-message.txt" \
  --out "$OUT_DIR/evaluation.json" \
  --pretty >/dev/null
"$PYTHON" "$ROOT_DIR/scripts/render_agent_handoff_dashboard.py" \
  --input-dir "$OUT_DIR" \
  --out "$OUT_DIR/dashboard.html"

echo "dashboard html: $OUT_DIR/dashboard.html"
echo "Agent handoff dashboard demo ok"

