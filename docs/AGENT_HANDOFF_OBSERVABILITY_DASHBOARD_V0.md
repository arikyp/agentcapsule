# Agent Handoff Observability Dashboard V0

The observability dashboard is a static HTML view over local handoff evidence.
It is meant for demos, pull request artifacts, CI attachments, and enterprise
review packets.

It does not run a server and does not call external APIs.

## Inputs

The renderer reads:

- `events.jsonl` from the handoff experiment
- `evaluation.json` from the transcript evaluator
- `policy-matrix-report.json` from the policy matrix runner

## Run

Ed25519 support is optional:

```bash
python3 -m pip install -e ".[signing]"
```

Run the full dashboard demo:

```bash
PYTHON=.venv/bin/python sh scripts/demo_agent_handoff_dashboard.sh
```

Or render from existing artifacts:

```bash
PYTHONPATH=src .venv/bin/python scripts/render_agent_handoff_dashboard.py \
  --input-dir /tmp/agent-handoff-policy-matrix \
  --out /tmp/agent-handoff-policy-matrix/dashboard.html
```

## View

Open the generated `dashboard.html` in a browser. The page shows:

- overall disposition
- event count
- evaluator score
- policy matrix pass count
- evaluator checklist
- policy scenario outcomes
- event timeline
- artifact paths

## Enterprise Role

This is not the final enterprise dashboard. It is a portable evidence packet.
The same artifact can be attached to a PR, audit ticket, agent run record, or CI
job output.

The later platform version can ingest the same JSON/JSONL artifacts into a
central UI without changing the handoff primitive.

