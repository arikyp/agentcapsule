# Agent To Agent Handoff Demo

This demo is the first observable Agent Capsule agent-to-agent experiment. It
models Agent A handing exact task state to Agent B through a text-native
message that contains both a readable summary and a signed capsule.

The demo is local and deterministic. It does not call external LLM APIs.

## Flow

1. Create an Agent A Ed25519 key pair.
2. Create a local Agent B trust registry containing Agent A's public key.
3. Bundle `examples/agent_handoff_demo/agent_a_workspace/`.
4. Pack and sign the bundle as an Agent Capsule.
5. Compose a text message with a human-readable summary plus the full capsule.
6. Scan the message under Agent B policy.
7. Verify the capsule under Agent B policy and registry trust.
8. Unpack the capsule into Agent B's sandbox output directory.
9. Compare decoded artifacts against Agent A's original workspace.
10. Emit `events.jsonl` with trace and audit evidence.

## Workspaces

- `examples/agent_handoff_demo/agent_a_workspace/` contains the source
  handoff artifacts.
- `examples/agent_handoff_demo/agent_b_workspace/` contains receiver notes and
  policy requiring an Ed25519 signature from Agent A's trusted key id.

The receiver policy requires registry trust and forbids inline public keys, so
`signature_verification: ok` is not enough. The handoff is accepted only when
`signature_trust.status: trusted` is also present.

## Run

Ed25519 support is optional:

```bash
python3 -m pip install -e ".[signing]"
```

Run the demo:

```bash
PYTHON=.venv/bin/python sh scripts/demo_agent_to_agent_handoff.sh
```

Or run the Python experiment directly:

```bash
PYTHONPATH=src .venv/bin/python scripts/run_agent_handoff_experiment.py --out-dir /tmp/agent-handoff-demo
```

The output directory contains:

- `agent-a.key`
- `agent-a.pub`
- `agent-b-trust-registry.json`
- `agent-a-handoff.capsule.txt`
- `agent-a-to-agent-b-message.txt`
- `agent-b-decoded/`
- `events.jsonl`

## JSONL Trace

`events.jsonl` includes custom handoff trace events and the existing
`agent_capsule_audit` events emitted by `scan`, `verify`, and `unpack`.

Expected decisions:

- `create_agent_a_keys`: `allow`
- `create_agent_b_trust_registry`: `allow`
- `pack_signed_handoff_capsule`: `allow`
- `compose_text_handoff_message`: `allow`
- `scan_text_message`: usually `review`, because the text channel contains a
  dense capsule payload even when the capsule is valid
- `verify_handoff_capsule`: `allow`
- `unpack_handoff_bundle`: `allow`
- `compare_decoded_artifacts`: `allow`

This is the intended governance shape: the channel scan can request review
while exact capsule verification and sandbox unpacking still produce strong
evidence for safe continuation.

