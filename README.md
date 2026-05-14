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
- Local policy, scan, audit, trust-registry, and encryption flows are implemented.
- Runtime Base64 capsule encode/decode is dependency-free Python; encryption and signing require `cryptography`.

## What Works

- Base64 capsule pack, inspect, verify, scan, and unpack flows.
- **AES-256-GCM authenticated encryption** for payload confidentiality.
- Signed capsule verification with HMAC and **Ed25519 public-key identities**.
- **Identity Registry** with support for organization binding, expiry, and revocation.
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

- Production identity (remote discovery), central trust registry, or remote policy service.
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
.venv/bin/python -m pip install -e ".[signing]"
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

Create an encrypted and signed handoff capsule:

```bash
export CAPSULE_KEY=$(openssl rand -base64 32)
agentcapsule pack payload.txt \
  --out capsule.txt \
  --encrypt aes-256-gcm \
  --encryption-key-env CAPSULE_KEY \
  --sign-ed25519-key publisher.key

agentcapsule inspect capsule.txt --encryption-key-env CAPSULE_KEY
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
