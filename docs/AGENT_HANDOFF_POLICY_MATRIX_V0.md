# Agent Handoff Policy Matrix V0

The policy matrix shows how one Agent A to Agent B handoff behaves under
multiple enterprise receiver policies.

The matrix is intentionally local. It uses the same signed handoff capsule,
trust registry, scanner, verifier, unpacker, and audit events that the handoff
demo already produces.

## Run

Ed25519 support is optional:

```bash
python3 -m pip install -e ".[signing]"
```

Run the matrix:

```bash
PYTHON=.venv/bin/python sh scripts/demo_agent_handoff_policy_matrix.sh
```

Or run the Python runner directly:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_agent_handoff_policy_matrix.py \
  --out-dir /tmp/agent-handoff-policy-matrix \
  --pretty
```

The output directory contains:

- `policy-matrix-report.json`
- `policy-matrix-events.jsonl`
- the generated handoff capsule, message, registry, decoded files, and
  evaluator artifacts from the base handoff experiment

## Scenarios

The default matrix is declared in
`examples/agent_handoff_demo/agent_b_workspace/policy-matrix.json`.

Default scenarios:

- `observe_signed_bundle`: permissive observation policy, expected `allow`
- `strict_registry_signed_bundle`: strict trusted Agent A policy, expected
  `allow`
- `strict_message_scan`: scan the text channel under strict policy, expected
  `review` because dense capsule text is present
- `wrong_agent_key_block`: policy trusts a different key id, expected `block`
- `payload_limit_block`: payload exceeds policy size limit, expected `block`
- `unsigned_handoff_block`: unsigned handoff under strict policy, expected
  `block`

Each scenario records:

- policy file
- artifact under test
- operation
- expected disposition
- observed disposition
- pass/fail
- full audit event

## Enterprise Use

This is the first practical shape of enterprise rollout testing:

```text
same agent handoff
  -> observe policy
  -> strict signed-registry policy
  -> wrong-key block policy
  -> payload-limit block policy
  -> unsigned block policy
  -> compare expected vs observed governance decisions
```

It gives reviewers confidence that policy changes do not silently weaken the
handoff gate.

