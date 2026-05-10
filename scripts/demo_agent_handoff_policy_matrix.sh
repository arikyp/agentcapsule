#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3}
OUT_DIR=${OUT_DIR:-$(mktemp -d)}

export PYTHONPATH="$ROOT_DIR/src${PYTHONPATH:+:$PYTHONPATH}"

if ! "$PYTHON" -c 'import cryptography' >/dev/null 2>&1; then
  echo "Agent handoff policy matrix requires the optional signing extra for Ed25519."
  echo 'Run: python3 -m pip install -e ".[signing]"'
  exit 0
fi

"$PYTHON" "$ROOT_DIR/scripts/run_agent_handoff_policy_matrix.py" --out-dir "$OUT_DIR" --pretty >/dev/null

echo "=== policy matrix ==="
"$PYTHON" - "$OUT_DIR/policy-matrix-report.json" <<'PY'
import json
import sys
from pathlib import Path

report = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
print(f"disposition: {report['disposition']}")
print(f"scenarios: {report['passed_scenarios']}/{report['scenario_count']} passed")
for scenario in report["scenarios"]:
    print(
        f"{scenario['name']}: expected={scenario['expected_disposition']} "
        f"observed={scenario['observed_disposition']} passed={scenario['passed']}"
    )
PY

echo "report: $OUT_DIR/policy-matrix-report.json"
echo "events: $OUT_DIR/policy-matrix-events.jsonl"
echo "Agent handoff policy matrix demo ok"

