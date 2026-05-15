# Agent Capsule

[![Tests](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml/badge.svg)](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentcapsule.svg)](https://pypi.org/project/agentcapsule/)
[![License](https://img.shields.io/pypi/l/agentcapsule.svg)](LICENSE)

Agent Capsule is a text-native container for exact machine-readable handoffs between agents.

It solves one core problem: agent-to-agent payloads often break when moved through chat, tickets, prompts, or email. Agent Capsule makes those payloads verifiable before use.

## Why Teams Adopt It

- Fewer broken handoffs: payload integrity is explicit (`payload_sha256`).
- Safer automation: verify before unpack/use.
- Better governance posture: local policy checks, audit-friendly flow, optional signature trust controls.
- Easy rollout: one CLI and one Python API, no service dependency required.

## What Engineers Get

- Deterministic envelope with metadata + hash.
- Delivery modes for real systems: inline, attachment, reference.
- Receiver kit with one command and one function.
- Optional hardening: HMAC/Ed25519, AES-256-GCM, zstd, resumable fetch.

## 60-Second Quickstart

```bash
python3 -m pip install agentcapsule
printf '{"task":"sync","items":[1,2,3]}\n' > payload.json
agentcapsule pack payload.json --out capsule.txt
agentcapsule verify capsule.txt
agentcapsule unpack capsule.txt --out decoded
cmp payload.json decoded/payload.json
```

If `cmp` prints nothing, the handoff is byte-perfect.

## Fast Integration Path

Without Agent Capsule:

- Payloads are often copied as free-form text.
- Truncation, formatting damage, or silent edits are common.
- Receivers lack a consistent trust and verification path.

With Agent Capsule:

- Payload integrity is explicit (`payload_sha256`).
- Signature and trust checks are policy-driven.
- Unpack happens only after verification.
- Receiver behavior is consistent across frameworks.

## Install

### PyPI

```bash
python3 -m pip install agentcapsule
```

### Full Optional Capabilities

```bash
python3 -m pip install "agentcapsule[all]"
```

Includes optional extras for signing, compression, and remote fetch.

### Project / CI Environment

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e ".[all]"
```

### pipx

```bash
pipx install agentcapsule
```

## Sender: Pack And Send

Pack payloads from file or directory:

```bash
agentcapsule pack handoff.json --out handoff.capsule.txt
```

Create a reference descriptor for out-of-band storage:

```bash
agentcapsule reference handoff.capsule.txt \
  --uri https://capsules.example/handoff/abc123 \
  --json > handoff.reference.json
```

## Receiver: Ingest Safely

CLI path:

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy policy.json --json
```

Python path:

```python
from agentcapsule import ingest_messages

result = ingest_messages(
    messages=thread_messages,
    out_dir="./sandbox",
    policy="./policy.json",
)

print(result.inline_capsules)
print(result.references)
print(result.unpacked_files)
```

This is the fastest way to integrate into an existing agent framework.

## Deploy In CI / Services

- CI: run `agentcapsule verify` as a gate before executing inbound artifacts.
- Services: call `ingest_messages(...)` in your receiver handler and pass your local policy file.
- Rollout model: start with unsigned Base64 + hash verification, then enforce signature trust policy by environment.

## Delivery Modes

- `inline`: full capsule in message body.
- `attachment`: full capsule as file/blob.
- `reference`: descriptor in message, full capsule fetched by URI.

Reference descriptors are not authoritative by themselves. Receivers must fetch the full capsule and verify `capsule_sha256`, payload hash, and policy requirements.

## Security And Trust Model

Baseline:

- SHA256 payload integrity checks.
- Local policy checks.
- Safe unpacking into chosen output directory.

Optional hardening:

- HMAC-SHA256 signatures.
- Ed25519 signatures and trust registry checks.
- AES-256-GCM payload encryption.
- Zstandard compression.
- Resumable reference fetching.

## Typical Production Flow

1. Sender packs payload and optional signature metadata.
2. Sender transports capsule inline/attachment/reference.
3. Receiver scans inbound text.
4. Receiver verifies metadata, hash, signature trust, and policy.
5. Receiver unpacks verified payload into sandbox.
6. Receiver executes downstream logic on unpacked files.

## Scope

Stable default path is Base64 capsule transfer and verification.

This repository also includes a `legacy/lmcodec/` subtree for historical LMCodec research and assets. Agent Capsule is the active project surface.

## Docs

- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/RECEIVER_GUIDE.md](docs/RECEIVER_GUIDE.md)
- [docs/INSTALL.md](docs/INSTALL.md)
- [docs/AGENT_CAPSULE_PROTOCOL_V0.md](docs/AGENT_CAPSULE_PROTOCOL_V0.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
