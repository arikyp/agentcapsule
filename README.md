# Agent Capsule

[![Tests](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml/badge.svg)](https://github.com/arikyp/agentcapsule/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/agentcapsule.svg)](https://pypi.org/project/agentcapsule/)
[![License](https://img.shields.io/pypi/l/agentcapsule.svg)](LICENSE)

Agent Capsule is the verifiable handoff format for agents.

It is a small open protocol + developer toolkit for safe agent handoffs. It wraps exact machine-readable payloads in a text-native envelope so receivers can detect, verify, policy-check, and unpack safely.

## 2-Minute Proof

```bash
python3 -m pip install agentcapsule
agentcapsule pack handoff.json --out capsule.txt
agentcapsule ingest thread.txt --out ./sandbox --strict --json
```

If ingest exits `0`, the handoff passed verification/policy and unpacked safely.
If ingest exits non-zero in `--strict`, treat it as a CI/governance failure.

## One Command, One Function

CLI:

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy ./policy.json --json --strict
```

Python:

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

## What It Solves

Normal agent channels are lossy for machine payloads (truncation, formatting drift, silent edits).
Agent Capsule turns handoffs into verifiable artifacts.

## Protocol Layers

- Capsule: exact payload bytes + metadata + hash/signature context.
- Envelope: text wire format with boundary markers, headers, and encoded payload.
- Manifest: handoff intent (creator, task, files, capabilities, policy hints).
- Delivery modes: inline, attachment, reference (URI + capsule hash + payload hash).

## Delivery Modes

- `inline`: full capsule in message body.
- `attachment`: full capsule as file/blob.
- `reference`: descriptor in message, full capsule fetched by URI.

Reference descriptors are not authoritative by themselves. Receivers must fetch the full capsule and verify `capsule_sha256`, `payload_sha256`, signature trust policy, and receiver policy.

## Not A Transport Platform

Agent Capsule does not replace transport. It travels through existing systems:
chat, tickets, email, GitHub, A2A/MCP workflows, and object storage.

## Security And Trust Model

Baseline:

- SHA256 payload integrity checks.
- Local policy checks.
- Safe unpacking into a chosen output directory.

Optional hardening:

- HMAC-SHA256 signatures.
- Ed25519 signatures and trust registry checks.
- AES-256-GCM payload encryption.
- Zstandard compression.
- Resumable reference fetching.

## Current Limitations

- No hosted trust service: signature trust resolution is local-file policy/registry driven.
- No remote/global key-discovery protocol yet: receivers must supply local trust inputs.
- No first-party JS/TS reference implementation yet.
- Governance output is JSON-first; there is no built-in long-running dashboard service.
- Reference fetching requires optional install extras (`agentcapsule[fetch]` or `agentcapsule[all]`).

## Typical Flow

1. Sender packs payload into a capsule.
2. Sender transports inline/attachment/reference.
3. Receiver scans and ingests.
4. Receiver verifies metadata, hashes, signature trust, and policy.
5. Receiver unpacks verified payload into sandbox.
6. Receiver runs downstream logic on unpacked files.

## Install

PyPI:

```bash
python3 -m pip install agentcapsule
```

Full optional capabilities:

```bash
python3 -m pip install "agentcapsule[all]"
```

Reference fetching support only:

```bash
python3 -m pip install "agentcapsule[fetch]"
```

## Docs

- [docs/QUICKSTART.md](docs/QUICKSTART.md)
- [docs/RECEIVER_GUIDE.md](docs/RECEIVER_GUIDE.md)
- [docs/INSTALL.md](docs/INSTALL.md)
- [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)
- [docs/AGENT_CAPSULE_PROTOCOL_V0.md](docs/AGENT_CAPSULE_PROTOCOL_V0.md)
- [docs/AGENT_CAPSULE_ED25519_DESIGN.md](docs/AGENT_CAPSULE_ED25519_DESIGN.md)
- [docs/AGENT_CAPSULE_AUDIT_LOG_V0.md](docs/AGENT_CAPSULE_AUDIT_LOG_V0.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
