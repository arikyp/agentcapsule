# Agent Capsule 📦

[![Tests](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml/badge.svg)](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentcapsule.svg)](https://pypi.org/project/agentcapsule/)
[![Python Version](https://img.shields.io/pypi/pyversions/agentcapsule.svg)](https://pypi.org/project/agentcapsule/)
[![License](https://img.shields.io/pypi/l/agentcapsule.svg)](LICENSE)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/arikyp/agentcapsule/graphs/commit-activity)

**The missing shipping container for exact, verifiable payloads between agents.** 
Secure, compressed, and identity-aware artifact transfer over chat, email, tickets, and A2A messages.

## Why Agent Capsule?

In multi-agent systems, "handoffs" often fail because LLMs lose payload fidelity when embedding data directly in conversation. Agent Capsule provides a standardized, machine-readable envelope that ensures:

- **Byte-Perfect Fidelity:** SHA256-verified roundtrips.
- **Confidentiality:** AES-256-GCM authenticated encryption.
- **Authenticity:** Ed25519 public-key identities and organization-aware trust.
- **Efficiency:** Zstandard compression for large payloads.
- **Interoperability:** Plug-and-play integrations for major frameworks.

---

## ⚡ Try In 30 Seconds

```bash
# Install with full security and compression support
pip install "agentcapsule[all]"

# Pack a directory into a secure, compressed capsule
agentcapsule pack ./workspace --out handoff.capsule.txt \
  --encrypt aes-256-gcm \
  --compression zstd

# Verify and unpack
agentcapsule verify handoff.capsule.txt
agentcapsule unpack handoff.capsule.txt --out ./received
```

---

## 🤝 Framework Integrations

### LangGraph
Agent Capsule makes LangGraph handoffs reliable and secure.

```python
from agentcapsule.integrations import LangGraphIntegration

# 1. Create a handoff message from a local workspace
handoff_msg = LangGraphIntegration.create_handoff_message(
    path="./agent_a_workspace",
    created_by="researcher_agent",
    encryption_key=MY_SECRET_KEY
)

# 2. In the receiving node, unpack the payload
files = LangGraphIntegration.unpack_handoff(
    message_content=state["messages"][-1].content,
    out_dir="./agent_b_workspace",
    encryption_key=MY_SECRET_KEY
)
```

### CrewAI & LlamaIndex
More official connectors for CrewAI, LlamaIndex, and AutoGen are coming soon. See [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

---

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
- Local policy, scan, audit, trust-registry, encryption, and scalability flows are implemented.
- Runtime Base64 capsule encode/decode is dependency-free Python; encryption, signing, and compression require optional extras.

## What Works

- Base64 capsule pack, inspect, verify, scan, and unpack flows.
- **AES-256-GCM authenticated encryption** for payload confidentiality.
- **Zstandard (zstd) compression** for efficient large-payload transfer.
- **Resumable Reference Fetching** via CLI for reliable large-artifact distribution.
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
- Large-file archival confidence.
- GPU-scale model training in the runtime path.

## Agent Capsule Quickstart

Use the PyPI package for a quick local try:

```bash
# Core package (Base64 only, no dependencies)
python3 -m pip install agentcapsule

# With full security and scalability support (recommended)
python3 -m pip install "agentcapsule[all]"
```

This exposes the `agentcapsule` and `capsule` commands for Agent Capsules.

For local development against the checkout:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[all]"
```

Create, inspect, verify, and unpack a compressed capsule:

```bash
printf 'large repetitive payload\n' > payload.txt
agentcapsule pack payload.txt --out capsule.txt --compression zstd
agentcapsule verify capsule.txt
```

Fetch and verify a capsule from a remote reference:

```bash
agentcapsule fetch --uri https://example.com/capsule.txt --sha256 <expected-hash> --out local.txt
# Or via reference descriptor
agentcapsule fetch --reference ref.json --out local.txt --resumable
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
For Ed25519 signing design details, see
[docs/AGENT_CAPSULE_ED25519_DESIGN.md](docs/AGENT_CAPSULE_ED25519_DESIGN.md).
For audit event schema and examples, see
[docs/AGENT_CAPSULE_AUDIT_LOG_V0.md](docs/AGENT_CAPSULE_AUDIT_LOG_V0.md).
For release and distribution planning, see
[docs/RELEASE_DISTRIBUTION.md](docs/RELEASE_DISTRIBUTION.md).
For the public roadmap, see [docs/ROADMAP.md](docs/ROADMAP.md).
