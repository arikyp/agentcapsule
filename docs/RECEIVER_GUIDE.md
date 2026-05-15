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

## Safe Receiver Order

Always apply this order:

1. Inspect and scan inbound message text.
2. Apply local policy checks.
3. If a reference descriptor is present, fetch referenced capsules and verify capsule SHA256.
4. Verify capsule integrity and authenticity (payload hash and signature trust policy).
5. Unpack into a sandbox directory.
6. Inspect unpacked files before execution/use.

## Notes

- `ingest_messages` handles inline capsules and JSON reference descriptors (`reference_type: agent_capsule_reference`).
- `malformed_blocks` in the ingest result reports capsule-like blocks with missing end markers.
- For HMAC signatures, pass `key_env`.
- For Ed25519 signatures, use `ed25519_public_key` and/or `signature_registry`.
