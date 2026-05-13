# Testing

The test suite relies on deterministic checks because the transport kernel is
meant to produce identical text for identical payload, model, and settings.

The stress tests use fixed pseudo-random seeds from the Python standard library.
They cover:

- Random payload roundtrips across empty, small, boundary, and multi-kilobyte payloads.
- Exact deterministic encode output for repeated calls.
- Single carrier-character mutation detection.
- Quantizer invariants for uniform, dominant-token, near-zero, invalid-float, and all-zero distributions.
- Range-coder roundtrips for fixed, changing, random, and highly skewed CDFs.

These tests intentionally do not use Hypothesis or external dependencies. If a
future property-test dependency is added, keep the current fixed-seed tests as
the stable regression baseline.

GitHub Actions runs the same dependency-free verification path on pull requests
and pushes to `main` across Python 3.11, 3.12, and 3.13:

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests
sh scripts/verify_v1.sh
python3 -m compileall src scripts tests
PYTHON=python3 sh scripts/demo_agent_capsule.sh
sh scripts/release_check.sh
```

The Agent Capsule demo exercises pack, inspect, verify, unpack, scan JSON,
codec registry output, and HMAC signing.
`scripts/demo_agent_capsule_ed25519.sh` additionally exercises the optional
`agentcapsule[signing]` Ed25519 prototype when `cryptography` is installed.
`scripts/demo_agent_capsule_registry.sh` exercises local Ed25519 trust registry
verification, rotated keys, revoked keys, and untrusted inline-key scan output.
`scripts/demo_agent_capsule_audit.sh` emits allow, review, and block audit
events, plus a registry-trusted signature event when `agentcapsule[signing]` is
installed.
`scripts/demo_agent_to_agent_handoff.sh` runs the first local Agent A to Agent B
handoff experiment, writes an `events.jsonl` trace, and evaluates the transcript
into `evaluation.json`.
`scripts/demo_agent_handoff_policy_matrix.sh` runs enterprise policy scenarios
against the same handoff and writes `policy-matrix-report.json`.
`scripts/demo_agent_handoff_dashboard.sh` renders a static HTML observability
dashboard from the handoff, evaluator, and policy matrix artifacts.

Known edge cases represented in the tests:

- Non-finite, negative, and zero probabilities are cleaned before quantization.
- All-zero probability input falls back to a uniform distribution.
- Every quantized token remains active with frequency at least one.
- Extremely skewed CDFs such as `(0, 1, 65536)` remain valid for range-coder roundtrip tests.
