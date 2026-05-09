# Agent Capsule Threat Model

Agent Capsule Protocol V0 is an artifact-transfer primitive for text-native AI
workflows. It is designed to make machine-readable payloads visible,
inspectable, policy-checkable, and byte-verifiable before a receiver unpacks
them.

V0 is not a complete trust system. It has SHA256 payload verification, optional
HMAC-SHA256 shared-secret authenticity, local policy checks, and scanner
heuristics. Public-key identity, encryption, registry trust, and SaaS
governance integrations are future layers.

## Assets

- Exact payload bytes carried inside the capsule.
- Plaintext metadata used for routing, inspection, and policy decisions.
- Local HMAC verification keys.
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
- use a valid HMAC key if the shared secret is compromised.

V0 does not assume the text channel preserves confidentiality. Capsule payload
text and metadata should be treated as readable by channel participants and
intermediaries unless a future encryption layer is used.

## Controls In V0

- Envelope boundaries are explicit and easy to scan.
- Required headers are rejected when missing.
- Payload bytes are decoded and checked against `payload_sha256`.
- Local policy can require known codecs, hashes, content types, payload size
  limits, sandbox unpacking, and HMAC signature mode.
- HMAC-SHA256 can authenticate a capsule when sender and receiver already share
  a secret.
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
5. Decode and recompute SHA256.
6. Unpack only into a sandbox directory.
7. Inspect decoded files before use.
8. Never execute decoded content as part of capsule verification.

## Residual Risks

- A receiver may apply an observe policy to a channel that should require
  signing.
- A leaked HMAC key lets an attacker produce valid signed capsules.
- Dense-text heuristics can produce false positives and false negatives.
- Inline n-gram model metadata is portable but bulky.
- V0 has no revocation, identity registry, encryption, DLP, SIEM, or central
  policy server.

## Deferred Design Work

The next design branch should specify Ed25519 public-key signing before any
implementation work. That design needs dependency, license, key discovery,
identity binding, rotation, revocation, and interoperability decisions.
The current proposal is documented in
[AGENT_CAPSULE_ED25519_DESIGN.md](AGENT_CAPSULE_ED25519_DESIGN.md).
