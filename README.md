# Agent Capsule

[![Tests](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml/badge.svg)](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentcapsule.svg)](https://pypi.org/project/agentcapsule/)
[![License](https://img.shields.io/pypi/l/agentcapsule.svg)](LICENSE)

The missing shipping container for exact, verifiable payloads between agents
over chat, email, tickets, and A2A messages.

## Try In 30 Seconds

```bash
python3 -m pip install agentcapsule
printf '{"task":"sync","items":[1,2,3]}\n' > payload.json
agentcapsule pack payload.json --out capsule.txt
agentcapsule verify capsule.txt
agentcapsule unpack capsule.txt --out decoded
cmp payload.json decoded/payload.json
```

Expected result:
- `verify` reports `ok`
- `cmp` prints nothing (byte-perfect roundtrip)

## Before/After In Practice

Before (free-form handoff text breaks machine parsing):

```text
{"task":"sync","items":[1,2,3
```

After (capsule-enveloped payload survives transport and verifies):

```text
-----BEGIN AGENT CAPSULE-----
...payload+metadata+sha256...
-----END AGENT CAPSULE-----
verify: ok
unpack: wrote decoded/payload.json
```

Agent Capsule Protocol V0 is an inspectable, verifiable artifact format for
moving exact machine-readable payloads through agent and text-native channels:
chat, tickets, prompts, email, GitHub issues, A2A messages, MIME attachments,
and agent traces.

The default capsule path is plain Base64 plus metadata, SHA256 verification,
optional signatures, local policy checks, and sandbox unpacking. Historical
research lives only in the archive, not the supported product surface.

## A2A Handoffs: Fixing The #1 Reliability Pain Point

A2A messages often lose payload fidelity when exact machine-readable data is
embedded directly in conversational fields. Capsules make that payload
verifiable, and reference mode keeps A2A messages small while preserving trust.

Reference-mode flow with A2A:

```bash
agentcapsule pack handoff.json --out handoff.capsule.txt
agentcapsule reference handoff.capsule.txt \
  --uri https://capsules.example/handoff/abc123 \
  --json > handoff.reference.json
```

Attach `handoff.reference.json` to the A2A message body. Receiving agents fetch
the referenced capsule, run `agentcapsule verify`, then `agentcapsule unpack`
into a sandboxed output directory before execution.

## Current Status

Agent Capsule V0 is the product-facing layer in this repository.

- Base64 capsules are the primary stable path.
- Capsules can be delivered inline, as attachments, or by reference descriptor.
- Directory bundles are deterministic JSON with per-file SHA256 and byte
  counts.
- HMAC-SHA256 and optional Ed25519 signatures are supported for authenticity
  experiments.
- Local policy, scan, audit, and trust-registry flows are implemented.
- Runtime Base64 capsule encode/decode is dependency-free Python.

## What Works

- Base64 capsule pack, inspect, verify, scan, and unpack flows.
- Signed capsule verification with HMAC and optional Ed25519.
- Agent handoff manifests with file inventory, requested capabilities, policy
  hints, and delivery mode.
- Inline, attachment, and reference delivery metadata.
- Byte-perfect encode/decode roundtrip for the tested payload sizes and demos.
- Deterministic output for identical payload, model, and settings.
- Model fingerprint checks before decode.
- Copy/paste armour with version, model fingerprint, and settings.
- CLI file encode/decode.
- CRC32 corruption detection inside the payload frame.
- Unit, stress, golden, and end-to-end verification tests.

## What Does Not Yet Work

- Production identity, central trust registry, or remote policy service.
- Encryption or privacy.
- Large-file distribution as an inline capsule.
- Semantically meaningful prose generation.
- Steganography-grade secrecy.
- Compression superiority over base64.
- Large-file archival confidence.
- GPU-scale model training in the runtime path.

## Agent Capsule Quickstart

Use the PyPI package for a quick local try:

```bash
python3 -m pip install agentcapsule
```

This exposes the `agentcapsule` and `capsule` commands for Agent Capsules.

For local development against the checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Create, inspect, verify, and unpack a Base64 capsule:

```bash
printf 'agent handoff state\n' > payload.txt
agentcapsule pack payload.txt --out capsule.txt
agentcapsule inspect capsule.txt
agentcapsule verify capsule.txt
agentcapsule unpack capsule.txt --out decoded
cmp payload.txt decoded/payload.txt
```

Create a signed handoff capsule with explicit manifest metadata:

```bash
CAPSULE_HMAC_KEY='shared secret' agentcapsule pack payload.txt \
  --out capsule.txt \
  --created-by agent-a \
  --task-id abc123 \
  --requested-capability read_files \
  --requested-capability run_tests \
  --delivery-mode inline \
  --sign-key-env CAPSULE_HMAC_KEY
CAPSULE_HMAC_KEY='shared secret' agentcapsule verify capsule.txt --key-env CAPSULE_HMAC_KEY
```

Emit a reference descriptor when the capsule will be stored out of band:

```bash
agentcapsule reference capsule.txt \
  --uri https://example.test/capsules/capsule.txt \
  --json
```

Tiny symmetric encryption example:

```bash
python3 -m pip install "agentcapsule[signing]"
python3 - <<'PY'
from cryptography.fernet import Fernet

key = Fernet.generate_key()
cipher = Fernet(key)
token = cipher.encrypt(b"handoff: exact payload")
print(token.decode())
print(cipher.decrypt(token).decode())
PY
```

Framework integration snippets:

```python
# LangGraph-style gate: verify before unpacking.
def ingest_capsule(path: str) -> dict:
    import subprocess

    subprocess.run(["agentcapsule", "verify", path], check=True)
    subprocess.run(["agentcapsule", "unpack", path, "--out", "decoded"], check=True)
    return {"payload_dir": "decoded"}
```

```python
# OpenAI Agents-style handoff: attach a reference descriptor instead of raw JSON.
handoff_message = {
    "content": "Capsule reference attached for exact payload transfer.",
    "attachments": [
        {
            "type": "agentcapsule.reference",
            "uri": "https://capsules.example/handoff/abc123",
        }
    ],
}
```

For a shorter developer path, see [docs/QUICKSTART.md](docs/QUICKSTART.md).
For installation packaging, see [docs/INSTALL.md](docs/INSTALL.md).
For release and distribution planning, see
[docs/RELEASE_DISTRIBUTION.md](docs/RELEASE_DISTRIBUTION.md).
For the public roadmap, see [docs/ROADMAP.md](docs/ROADMAP.md).

## Agent Capsule Commands

Capsules are inspectable text artifacts that wrap exact machine-readable
payloads with plaintext metadata, SHA256 verification, and safe unpack flows.
The command examples below use Base64 unless a different backend is selected
explicitly. `capsule` remains an alias for `agentcapsule`.

```bash
agentcapsule pack examples/agent_capsule_demo/handoff --out capsule.txt
agentcapsule inspect capsule.txt
agentcapsule verify capsule.txt
agentcapsule unpack capsule.txt --out decoded
agentcapsule scan capsule.txt
agentcapsule codecs
agentcapsule inspect capsule.txt --json
CAPSULE_HMAC_KEY='shared secret' agentcapsule pack payload.bin --out capsule.txt --sign-key-env CAPSULE_HMAC_KEY
agentcapsule keys generate --private-key publisher.key --public-key publisher.pub
agentcapsule pack payload.bin --out capsule.txt --sign-ed25519-key publisher.key --signature-key-id publisher
agentcapsule verify capsule.txt --ed25519-public-key publisher.pub
agentcapsule verify capsule.txt --signature-registry trusted-keys.json
agentcapsule verify capsule.txt --audit-json
```

Core capsule, HMAC, and base64 workflows work with the default
dependency-free install. Ed25519 demos/tests require the optional signing extra:

```bash
python3 -m pip install -e ".[signing]"
```

For Ed25519, distinguish validity from trust: `signature_verification: ok`
means the capsule was signed by the matching key; `signature_trust.status:
trusted` means the key also passed local registry and policy checks.

`capsule scan --json` emits typed findings with source locations for governance
logs and agent traces. `--audit-json` on `inspect`, `verify`, `unpack`, and
`scan` emits a consistent allow/review/block governance event.

See [docs/AGENT_CAPSULE_PROTOCOL_V0.md](docs/AGENT_CAPSULE_PROTOCOL_V0.md) and
[docs/AGENT_CAPSULE_PRODUCT_BRIEF.md](docs/AGENT_CAPSULE_PRODUCT_BRIEF.md).
For security assumptions, HMAC limits, and governance policy examples, see
[docs/AGENT_CAPSULE_THREAT_MODEL.md](docs/AGENT_CAPSULE_THREAT_MODEL.md).
For the public-key signing proposal, see
[docs/AGENT_CAPSULE_ED25519_DESIGN.md](docs/AGENT_CAPSULE_ED25519_DESIGN.md).
For structured governance events, see
[docs/AGENT_CAPSULE_AUDIT_LOG_V0.md](docs/AGENT_CAPSULE_AUDIT_LOG_V0.md).
For an observable agent-to-agent handoff experiment, see
[docs/AGENT_TO_AGENT_HANDOFF_DEMO.md](docs/AGENT_TO_AGENT_HANDOFF_DEMO.md).
The handoff demo writes `events.jsonl` plus an evaluator report that checks the
summary, capsule, registry-trusted signature, sandbox unpack, and artifact
comparison evidence.
For enterprise policy tiers, see
[docs/AGENT_HANDOFF_POLICY_MATRIX_V0.md](docs/AGENT_HANDOFF_POLICY_MATRIX_V0.md).
For a static observability view over handoff evidence, see
[docs/AGENT_HANDOFF_OBSERVABILITY_DASHBOARD_V0.md](docs/AGENT_HANDOFF_OBSERVABILITY_DASHBOARD_V0.md).
For the central trust registry direction, see
[docs/AGENT_CAPSULE_CENTRAL_TRUST_REGISTRY.md](docs/AGENT_CAPSULE_CENTRAL_TRUST_REGISTRY.md).

## Verification

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Legacy V1 fixture verification:

```bash
sh scripts/verify_v1.sh
```

Installed CLI release check:

```bash
sh scripts/release_check.sh
```

## Demo And Experiment Scripts

```bash
sh scripts/demo_roundtrip.sh
```

Compare the fixed carrier against the trained order-1 n-gram carrier:

```bash
sh scripts/demo_compare.sh
```

Run the pinned Transformer carrier demo:

```bash
sh scripts/demo_transformer.sh
```

Create deterministic carrier corpora and train/held-out splits:

```bash
scripts/build_carrier_corpus.py \
  --out examples/carrier_corpus_v2.txt \
  --lines 5000 \
  --seed 42 \
  --domain mixed
scripts/split_corpus.py \
  --input examples/carrier_corpus_v2.txt \
  --train-out examples/carrier_train_v2.txt \
  --heldout-out examples/carrier_heldout_v2.txt \
  --heldout-ratio 0.20 \
  --filter-vocab
```

Optional PyTorch training/export is available in
`scripts/train_transformer_torch.py`. PyTorch is only needed for that exporter;
the exported JSON model loads through the dependency-free `TransformerLM`
runtime.

## Documentation

- [docs/README.md](docs/README.md): minimal docs index.
- [docs/INSTALL.md](docs/INSTALL.md): install options including `pipx`.
- [docs/ROADMAP.md](docs/ROADMAP.md): public roadmap and near-term priorities.

## Community

- Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
- Use the issue templates for bug reports and feature requests.
- Track roadmap items in [docs/ROADMAP.md](docs/ROADMAP.md).
- [docs/QUICKSTART.md](docs/QUICKSTART.md): installed CLI usage.
- [docs/AGENT_CAPSULE_PROTOCOL_V0.md](docs/AGENT_CAPSULE_PROTOCOL_V0.md):
  Agent Capsule V0 envelope, backends, verification, and scan flow.
- [docs/AGENT_CAPSULE_PRODUCT_BRIEF.md](docs/AGENT_CAPSULE_PRODUCT_BRIEF.md):
  product pivot brief and governance roadmap.
- [docs/RELEASE_DISTRIBUTION.md](docs/RELEASE_DISTRIBUTION.md): release and
  publishing path.
- [docs/TESTING.md](docs/TESTING.md): stress/property test strategy.
- [schemas/benchmark_result_v1.json](schemas/benchmark_result_v1.json):
  benchmark JSON schema contract.
- [CHANGELOG.md](CHANGELOG.md): release notes.
- [LICENSE](LICENSE): Apache-2.0 terms.

## Legacy V1 Fixtures

All golden fixtures use payload `bytes(range(256))`.

Payload SHA256:

```text
40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880
```

Fixed carrier:

- Message fixture: [tests/fixtures/golden_message_v1.txt](tests/fixtures/golden_message_v1.txt)
- Model fingerprint: `d60583f4d741e42cb713b11c78b8ffc89cda1ee05eca522929bec8cbdb423be8`
- Message SHA256: `f53ec3604a378788b20cf6e0aadbfe441a063aa7ce1cea0bef9b1427cbd21e35`

Order-1 n-gram carrier fixture:

- Model fixture: [tests/fixtures/ngram_model_v1.json](tests/fixtures/ngram_model_v1.json)
- Message fixture: [tests/fixtures/ngram_golden_message_v1.txt](tests/fixtures/ngram_golden_message_v1.txt)
- Model fingerprint: `b1cd62a9019b67e0a42913dac1dca09852b4931f09afa87bb8e62089fe184a3a`
- Message SHA256: `53c062a238764c72caa9dd338d37682ab350d7ace4251e9778ba13ae97d99512`

Transformer carrier fixture:

- Model fixture: [tests/fixtures/transformer_model_v1.json](tests/fixtures/transformer_model_v1.json)
- Message fixture: [tests/fixtures/transformer_golden_message_v1.txt](tests/fixtures/transformer_golden_message_v1.txt)
- Settings: `SHAPE_UNIFORM_MIX=0.80; TEMPERATURE=1.25`
- Model fingerprint: `cfc75d7b54524f7a09a90454d89768aa4eb75b17546607c376760e2fc9d8f851`
- Message SHA256: `7713a0b7208462485f854ab58e5423f16c16360aeff524f1597ba49c840ad96b`

Regenerate golden fixtures only after intentional codec changes:

```bash
python3 scripts/generate_golden.py
```
