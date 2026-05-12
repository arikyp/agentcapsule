# Agent Capsule Developer Quickstart

Agent Capsules wrap exact machine-readable payloads in an inspectable envelope
with metadata, SHA256 verification, optional signatures, and safe unpack flows.
The default path is Base64. LMCodec carriers are advanced/research backends.

## Install

From the repository root:

```bash
python3 -m pip install -e .
```

This exposes `agentcapsule`, `capsule`, and `lmcodec` commands from
`pyproject.toml`. `agentcapsule` is the primary Agent Capsule command.

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

## Advanced LMCodec Carrier

The LMCodec CLI maps bytes into copy/paste-safe carrier text and decodes that
text back to the exact original bytes. This is a research backend; start with
Base64 capsules unless you specifically need carrier-shaping experiments.

Create a binary sample:

```bash
python3 - <<'PY'
from pathlib import Path
Path("/tmp/lmcodec-payload.bin").write_bytes(bytes(range(256)))
PY
```

Encode and decode with the stable fixed carrier:

```bash
lmcodec encode --in /tmp/lmcodec-payload.bin --out /tmp/lmcodec-message.txt --wrap 80
lmcodec decode --in /tmp/lmcodec-message.txt --out /tmp/lmcodec-output.bin
cmp /tmp/lmcodec-payload.bin /tmp/lmcodec-output.bin
```

The Transformer carrier is experimental and pinned as a V1 fixture:

```bash
lmcodec encode \
  --model tests/fixtures/transformer_model_v1.json \
  --in /tmp/lmcodec-payload.bin \
  --out /tmp/lmcodec-transformer-message.txt \
  --wrap 80 \
  --shape-uniform-mix 0.80 \
  --temperature 1.25 \
  --max-steps 100000

lmcodec decode \
  --model tests/fixtures/transformer_model_v1.json \
  --in /tmp/lmcodec-transformer-message.txt \
  --out /tmp/lmcodec-transformer-output.bin

cmp /tmp/lmcodec-payload.bin /tmp/lmcodec-transformer-output.bin
```

## Verify The Release

Run:

```bash
sh scripts/release_check.sh
```

For lower-level V1 fixture verification:

```bash
sh scripts/verify_v1.sh
```
