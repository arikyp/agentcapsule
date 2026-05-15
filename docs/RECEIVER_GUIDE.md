# How To Receive an Agent Capsule Safely

This guide is the adoption path for receivers.

Use one API call when integrating into an agent framework:

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

Use one CLI command for transcripts:

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy policy.json --json
```

For CI/governance gates, use strict mode:

```bash
agentcapsule ingest thread.txt --out ./sandbox --policy policy.json --json --strict
```

## Safe Receiver Order

Always apply this order:

1. Inspect and scan inbound message text.
2. Apply local policy checks.
3. If a reference descriptor is present, fetch referenced capsules and verify capsule SHA256.
4. Validate descriptor `payload_sha256` against the fetched capsule metadata.
5. Verify capsule integrity and authenticity (payload hash and signature trust policy).
6. Unpack into a sandbox directory.
7. Inspect unpacked files before execution/use.

## Notes

- `ingest_messages` handles inline capsules and JSON reference descriptors (`reference_type: agent_capsule_reference`).
- Reference descriptors must include both `capsule_sha256` and `payload_sha256`.
- `malformed_blocks` in the ingest result reports capsule-like blocks with missing end markers.
- `scan_report` in the ingest result includes a governance scan summary and findings for the full message set.
- For HMAC signatures, pass `key_env`.
- For Ed25519 signatures, use `ed25519_public_key` and/or `signature_registry`.
- Reference fetching requires `agentcapsule[fetch]` (or `agentcapsule[all]`) so `httpx` is installed.
