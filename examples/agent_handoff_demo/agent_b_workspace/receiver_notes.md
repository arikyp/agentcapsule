# Agent B Receiver Notes

Agent B accepts handoffs only after local inspection, registry-backed signature
verification, sandbox unpacking, and artifact comparison.

The demo policy requires an Ed25519 signature from the expected Agent A key id
and a trusted local signature registry entry.

