# Agent Capsule Threat Model

Agent Capsule Protocol V0 is an artifact-transfer primitive for text-native AI
workflows. It is designed to make machine-readable payloads visible,
inspectable, policy-checkable, and byte-verifiable before a receiver unpacks
them.

V0 is not a complete trust system. It has SHA256 payload verification, optional
HMAC-SHA256 shared-secret authenticity, optional Ed25519 public-key
authenticity, local JSON trust registries, local policy checks, and scanner
heuristics. Remote public-key identity, encryption, and SaaS governance
integrations are future layers.

## Assets

- Exact payload bytes carried inside the capsule.
- Plaintext metadata used for routing, inspection, and policy decisions.
- Local HMAC verification keys and Ed25519 public/private key files.
- Decoded output directory and any downstream tools that may consume it.
- Audit events emitted by `capsule inspect`, `capsule verify`, and
  `capsule scan --json`.

## Trust Boundaries

- Text channel boundary: chat, ticket, email, issue, prompt, or trace text can
  be edited, copied, truncated, or surrounded by unrelated content.
- Capsule parser boundary: metadata is untrusted until parsed and checked.
- Payload decode boundary: decoded bytes are untrusted even after hash
  verification.
- Unpack boundary: files must be written only under the requested output
  directory.
- Execution boundary: Agent Capsule tooling never executes decoded content.

## Attacker Model

V0 assumes an attacker may:

- insert capsule-like text into a channel,
- modify capsule headers or payload text,
- remove or reorder text around a capsule,
- add invisible Unicode or dense opaque blocks,
- attempt bundle path traversal,
- send oversized payloads,
- send unsigned capsules to a channel that expects signed capsules,
- use a valid HMAC key if the shared secret is compromised,
- sign with an Ed25519 key that is valid cryptographically but not trusted for
  the channel.

V0 does not assume the text channel preserves confidentiality. Capsule payload
text and metadata should be treated as readable by channel participants and
intermediaries unless a future encryption layer is used.

## Controls In V0

- Envelope boundaries are explicit and easy to scan.
- Required headers are rejected when missing.
- Payload bytes are decoded and checked against `payload_sha256`.
- Local policy can require known codecs, hashes, content types, payload size
  limits, sandbox unpacking, HMAC signature mode, and Ed25519 signature mode.
- HMAC-SHA256 can authenticate a capsule when sender and receiver already share
  a secret.
- Ed25519 can verify that a capsule was signed by a public key; trust in that
  key comes from local policy and the local registry.
- Directory bundles reject absolute paths and `..` traversal.
- Scanner findings flag explicit capsules, invalid capsules, malformed
  capsule-like blocks, base64-like dense text, long dense lines, and invisible
  Unicode.

## HMAC-SHA256 Semantics

HMAC-SHA256 in V0 is a shared-secret integrity and authenticity check. It means:

- someone with the same secret key produced the signed capsule text,
- changing signed headers or payload text invalidates verification,
- policy can reject unsigned capsules by requiring `hmac-sha256`.

It does not mean:

- public identity,
- non-repudiation,
- automatic key discovery,
- proof that a named person authored the capsule,
- protection if the shared secret leaks,
- encryption or privacy.

Operators should treat `signature_key_id` as a key lookup hint, not as an
identity claim. Receivers still need a trusted local mapping from key ID to key
material and channel expectations.

## Policy Examples

Observe-only channel:

```json
{
  "require_known_codec": true,
  "require_hash": true,
  "allow_unsigned": true,
  "required_signature_modes": [],
  "allowed_content_types": [
    "application/octet-stream",
    "application/vnd.agent.bundle+json"
  ],
  "max_payload_bytes": 16777216,
  "decode_to_sandbox_required": true
}
```

Signed handoff channel:

```json
{
  "require_known_codec": true,
  "require_hash": true,
  "allow_unsigned": false,
  "required_signature_modes": [
    "hmac-sha256"
  ],
  "allowed_content_types": [
    "application/octet-stream",
    "application/vnd.agent.bundle+json"
  ],
  "max_payload_bytes": 1048576,
  "decode_to_sandbox_required": true
}
```

Small signed bundle channel:

```json
{
  "require_known_codec": true,
  "require_hash": true,
  "allow_unsigned": false,
  "required_signature_modes": [
    "hmac-sha256"
  ],
  "allowed_content_types": [
    "application/vnd.agent.bundle+json"
  ],
  "max_payload_bytes": 262144,
  "decode_to_sandbox_required": true
}
```

The committed examples live under `examples/agent_capsule_demo/`.

## Governance Dispositions

`capsule scan` maps scanner risk into an operational disposition:

- `low` -> `allow`
- `medium` -> `review`
- `high` -> `block`

This is intentionally simple. It is a local report format for demos, CI, and
agent traces, not a final enterprise enforcement engine.

## Safe Receive Flow

1. Scan the surrounding text.
2. Parse capsule metadata.
3. Apply local policy.
4. Verify HMAC if the policy or channel requires it.
5. Verify Ed25519 if the policy or channel requires public-key signatures.
6. Decode and recompute SHA256.
7. Unpack only into a sandbox directory.
8. Inspect decoded files before use.
9. Never execute decoded content as part of capsule verification.

## Residual Risks

- A receiver may apply an observe policy to a channel that should require
  signing.
- A leaked HMAC key lets an attacker produce valid signed capsules.
- An inline Ed25519 public key proves signature validity, not trust in the key.
- A leaked Ed25519 private key lets an attacker produce valid signed capsules
  for that key until local policy or a future registry revokes it.
- A stale local registry may continue trusting a key after an organization
  considers it expired or compromised.
- Dense-text heuristics can produce false positives and false negatives.
- Inline n-gram model metadata is portable but bulky.
- V0 has local revocation only. It has no remote identity registry, encryption,
  DLP, SIEM, or central policy server.

## Deferred Design Work

The current public-key signing and local registry design is documented in
[AGENT_CAPSULE_ED25519_DESIGN.md](AGENT_CAPSULE_ED25519_DESIGN.md). Remote
registry, identity binding, expiry windows, and transparency logs remain
deferred.
