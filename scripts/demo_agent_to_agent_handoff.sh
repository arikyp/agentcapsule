#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
OUT_DIR=${OUT_DIR:-$(mktemp -d)}

export PYTHONPATH="$ROOT_DIR/src:$ROOT_DIR/legacy/lmcodec/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON" -c 'import cryptography' >/dev/null 2>&1; then
  echo "Agent handoff demo requires the optional signing extra for Ed25519."
  echo 'Run: python3 -m pip install -e ".[signing]"'
  exit 0
fi

"$PYTHON" "$ROOT_DIR/scripts/run_agent_handoff_experiment.py" --out-dir "$OUT_DIR"
"$PYTHON" "$ROOT_DIR/scripts/evaluate_agent_handoff_transcript.py" \
  --events "$OUT_DIR/events.jsonl" \
  --message "$OUT_DIR/agent-a-to-agent-b-message.txt" \
  --out "$OUT_DIR/evaluation.json" \
  --pretty >/dev/null

echo "=== events.jsonl ==="
"$PYTHON" - "$OUT_DIR/events.jsonl" <<'PY'
import json
import sys
from pathlib import Path

for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    event = json.loads(line)
    operation = event.get("step") or event.get("operation")
    disposition = event.get("disposition")
    result = event.get("result", {})
    print(f"{operation}: {disposition}")
    if operation == "compare_decoded_artifacts":
        print(f"  match: {result.get('match')}")
PY

echo "=== evaluation ==="
"$PYTHON" - "$OUT_DIR/evaluation.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"disposition: {report['disposition']}")
print(f"score: {report['score']}")
for check in report["checks"]:
    print(f"{check['id']}: {check['status']}")
PY

echo "Agent to agent handoff demo ok"
