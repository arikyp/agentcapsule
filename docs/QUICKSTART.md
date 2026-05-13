# Agent Capsule Developer Quickstart

Agent Capsules wrap exact machine-readable payloads in an inspectable envelope
with metadata, SHA256 verification, optional signatures, and safe unpack flows.
The default path is Base64.

## Install

From the repository root:

```bash
python3 -m pip install -e .
```

This exposes `agentcapsule` and `capsule` commands from `pyproject.toml`.
`agentcapsule` is the primary Agent Capsule command.

## Pack And Verify A Capsule

Create a sample payload:

```bash
printf 'agent handoff state\n' > /tmp/capsule-payload.txt
```

Pack it with the primary Base64 path:

```bash
agentcapsule pack /tmp/capsule-payload.txt --out /tmp/capsule.txt
```

Inspect metadata before decode:

```bash
agentcapsule inspect /tmp/capsule.txt
```

Verify and unpack:

```bash
agentcapsule verify /tmp/capsule.txt
agentcapsule unpack /tmp/capsule.txt --out /tmp/capsule-decoded
cmp /tmp/capsule-payload.txt /tmp/capsule-decoded/capsule-payload.txt
```

## Add Handoff Metadata

```bash
agentcapsule pack /tmp/capsule-payload.txt \
  --out /tmp/agent-a-handoff.capsule.txt \
  --created-by agent-a \
  --task-id abc123 \
  --requested-capability read_files \
  --requested-capability run_tests \
  --policy-hint sandbox_required=true \
  --policy-hint network_egress=false \
  --delivery-mode inline
agentcapsule inspect /tmp/agent-a-handoff.capsule.txt --json
```

## Delivery Modes

Inline delivery pastes the full capsule into the message body:

```bash
agentcapsule pack /tmp/capsule-payload.txt --out /tmp/inline.capsule.txt --delivery-mode inline
```

Attachment delivery sends the same capsule envelope as a file or blob:

```bash
agentcapsule pack /tmp/capsule-payload.txt --out /tmp/attachment.capsule.txt --delivery-mode attachment
```

Reference delivery sends a descriptor while the full capsule lives elsewhere:

```bash
agentcapsule pack /tmp/capsule-payload.txt \
  --out /tmp/reference.capsule.txt \
  --delivery-mode reference \
  --delivery-uri https://example.test/capsules/reference.capsule.txt
agentcapsule reference /tmp/reference.capsule.txt \
  --uri https://example.test/capsules/reference.capsule.txt \
  --json
```

Receivers must fetch the full capsule and verify its `capsule_sha256`,
payload hash, and signature. The descriptor is not authoritative.

## Sign A Capsule

```bash
CAPSULE_HMAC_KEY='shared secret' agentcapsule pack /tmp/capsule-payload.txt \
  --out /tmp/signed.capsule.txt \
  --sign-key-env CAPSULE_HMAC_KEY \
  --signature-key-id dev-shared-key
CAPSULE_HMAC_KEY='shared secret' agentcapsule verify /tmp/signed.capsule.txt --key-env CAPSULE_HMAC_KEY
```

## Verify The Release

Run:

```bash
sh scripts/release_check.sh
```

For historical fixture verification only:

```bash
sh scripts/verify_v1.sh
```
