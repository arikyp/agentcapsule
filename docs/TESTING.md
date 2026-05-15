# Testing

The Agent Capsule suite focuses on deterministic envelope, verification, policy,
fetch, scan, and unpack behavior.

GitHub Actions runs this verification path on pull requests and pushes to
`main` across Python 3.11, 3.12, and 3.13:

```bash
python3 -m pip install -e .
PYTHONPATH=src:legacy/lmcodec/src python3 -m unittest discover -s tests
python3 -m compileall src scripts tests
PYTHON=python3 sh scripts/demo_agent_capsule.sh
sh scripts/release_check.sh
```

Any test or demo path that exercises Ed25519 signing or registry-trusted
verification must install the optional signing extra first:

```bash
python3 -m pip install -e ".[signing]"
```

`scripts/demo_agent_capsule_ed25519.sh` exercises optional Ed25519 signing when
`cryptography` is installed.
`scripts/demo_agent_capsule_registry.sh` exercises local Ed25519 trust-registry
verification, rotated keys, revoked keys, and untrusted inline-key scan output.
`scripts/demo_agent_capsule_audit.sh` emits allow/review/block audit events.
`scripts/demo_agent_to_agent_handoff.sh` runs a local Agent A to Agent B
handoff experiment and writes an `events.jsonl` trace.
`scripts/demo_agent_handoff_policy_matrix.sh` runs enterprise policy scenarios
against the same handoff and writes `policy-matrix-report.json`.
`scripts/demo_agent_handoff_dashboard.sh` renders a static HTML observability
dashboard from handoff artifacts.

Legacy LMCodec fixture verification lives at:

```bash
sh legacy/lmcodec/scripts/verify_v1.sh
```
