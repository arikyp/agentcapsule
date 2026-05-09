# Agent Capsule Ed25519 Signing Design

This document specifies the Ed25519 public-key signing layer for Agent Capsule
Protocol. The implementation is intentionally narrow: optional dependency,
local key files, inline public key mode, and local JSON trust registry mode. It
does not implement remote registry or organization identity services.

## Decision Summary

- Add a signature mode named `ed25519`.
- Keep core `dependencies = []`; expose crypto support through the optional
  `signing` extra.
- Reuse the existing canonical signed bytes produced by
  `agentcapsule.signing.signed_bytes`.
- Store signatures as header metadata, not inside the decoded payload.
- Treat public-key identity, trust policy, rotation, and revocation as local
  registry concerns for now.
- Implement Ed25519 as an optional capability first, then decide whether it
  belongs in the default install.

## Why Ed25519

HMAC-SHA256 is useful for V0 demos and shared-secret channels, but it does not
provide public identity or non-repudiation. Ed25519 gives Agent Capsules a
compact public-key signature mode that can support:

- publisher identity,
- verification without sharing signing secrets,
- key rotation and audit trails,
- signatures that survive movement through text-native channels,
- future enterprise policy rules such as trusted publishers or allowed key
  fingerprints.

## Non-Goals

This design does not specify:

- encryption,
- certificate authority semantics,
- web PKI integration,
- central policy service APIs,
- hardware security module support,
- transparency log implementation,
- remote registry implementation,
- automatic trust in any key shipped inside a capsule.

## Signature Mode

Proposed metadata:

```text
signature: ed25519
signature_key_id: <publisher-controlled key id>
signature_public_key_fingerprint: <sha256 of canonical public key bytes>
signature_public_key_encoding: base64
signature_public_key: <optional inline public key>
signature_value_encoding: base64
signature_value: <base64 Ed25519 signature>
```

Rules:

- `signature` identifies the verification algorithm.
- `signature_key_id` is a lookup hint, not an identity proof.
- `signature_public_key_fingerprint` is required for signed capsules.
- `signature_public_key` is optional because registry mode should not require
  embedding the public key in every capsule.
- `signature_value` signs canonical capsule bytes.
- Unknown signature modes remain verification failures.

The existing parser already tolerates additional headers and renders them in a
stable order after known headers. A future implementation should add these
headers to `HEADER_ORDER` for readability.

## Signing Input

The signing input should remain:

```text
AGENT-CAPSULE-SIGNATURE-V0
<sorted header lines except signature_value>

<payload text>
```

This is the same canonical input used by V0 HMAC signing. Keeping one signing
input avoids subtle policy differences between shared-secret and public-key
signatures.

Implementation requirements:

- exclude `signature_value`,
- include every other header exactly as parsed or generated,
- include encoded payload text, not decoded payload bytes,
- normalize rendered line endings to LF before signing,
- verify the payload SHA256 separately after signature verification.

The signature proves the capsule text and metadata were signed. The payload hash
still proves decoded bytes match `payload_sha256`.

## Key Encoding

Use raw 32-byte Ed25519 public keys and base64 encode them in capsule metadata.

Fingerprint:

```text
sha256(raw_public_key_bytes).hexdigest()
```

Private keys should never be written into capsules. CLI signing should read a
private key from an explicit path or environment reference, not from generic
process state.

## Trust Modes

Inline key mode:

- capsule includes `signature_public_key`,
- verifier can check the signature without a registry,
- useful for demos, offline transfer, and bootstrap channels,
- does not prove the key should be trusted.

Registry key mode:

- capsule includes key ID and fingerprint,
- verifier resolves the public key through a local JSON registry,
- policy decides whether the publisher, key, or fingerprint is allowed,
- better for enterprise governance and audit.

Inline mode answers "did this key sign this capsule?" Registry mode answers
"is this signing key trusted for this channel?"

## Policy Extensions

Policy fields:

```json
{
  "required_signature_modes": ["ed25519"],
  "trusted_signature_key_ids": ["publisher-prod-2026q2"],
  "trusted_signature_key_fingerprints": ["<sha256>"],
  "allow_inline_public_keys": false,
  "require_signature_registry": true,
  "max_signature_age_seconds": 2592000
}
```

V0 policy already supports `required_signature_modes`, so a future
implementation can require `ed25519` without changing that field.
`require_signature_registry`, `allow_inline_public_keys`,
`trusted_signature_key_ids`, and `trusted_signature_key_fingerprints` are
implemented for local policy enforcement. `max_signature_age_seconds` remains
deferred.

## CLI Shape

Proposed commands:

```bash
capsule keys fingerprint --public-key publisher.pub
capsule pack payload.bin --out capsule.txt \
  --sign-ed25519-key publisher.key \
  --signature-key-id publisher-prod-2026q2
capsule verify capsule.txt --ed25519-public-key publisher.pub
capsule verify capsule.txt --signature-registry trusted-keys.json
capsule keys registry-entry --key-id publisher-prod-2026q2 --public-key publisher.pub
```

Compatibility rules:

- Existing `--sign-key-env` remains HMAC-only.
- HMAC verification continues to use `--key-env`.
- Ed25519 signing should use explicit Ed25519 flag names.
- `capsule inspect` should show signature mode, key ID, key fingerprint,
  signature verification status, and whether the key came from inline metadata
  or registry lookup.

## Dependency Posture

Python standard library does not provide Ed25519 signing today, so real
implementation requires either an external package or a delegated system tool.

Candidate packages:

- `cryptography`: broad PyCA package, current PyPI metadata reports
  `Apache-2.0 OR BSD-3-Clause`, actively maintained, larger dependency surface.
- `PyNaCl`: PyCA/libsodium binding, current PyPI metadata reports
  `Apache-2.0`, focused NaCl API, depends on libsodium packaging.
- pure-Python or legacy `ed25519` packages: smaller surface, but generally less
  attractive for production security and maintenance.

Recommendation:

1. Keep core `lmcodec` dependency-free.
2. Implement Ed25519 behind an optional extra, for example:

   ```toml
   [project.optional-dependencies]
   signing = ["cryptography>=46,<47"]
   ```

3. Prefer `cryptography` unless implementation testing shows packaging or API
   friction that makes `PyNaCl` better.
4. Re-check license, wheel, platform, and Python-version metadata immediately
   before implementation.

This keeps the transport codec usable in minimal environments while allowing a
production-grade signing path for deployments that opt in.

## Verification Order

Verifier flow:

1. Parse envelope.
2. Apply metadata policy.
3. Resolve public key from inline metadata or registry.
4. Verify Ed25519 signature over canonical signed bytes.
5. Decode payload text.
6. Verify `payload_sha256`.
7. Apply payload size/content policy.
8. Unpack only under the requested sandbox directory.

Signature verification should happen before payload decode when possible. Hash
verification still happens after decode because the hash covers decoded bytes.

## Failure Modes

Return non-zero verification failures for:

- unsupported signature mode,
- missing signature value,
- malformed signature value,
- missing public key or registry entry,
- public key fingerprint mismatch,
- signature verification failure,
- signature mode disallowed by policy,
- payload SHA256 mismatch after successful signature verification.

Error messages should identify the failing class without leaking private key
material or registry internals.

## Test Plan

Implementation branch tests should cover:

- deterministic canonical signed bytes,
- valid Ed25519 capsule verifies,
- modified payload text fails signature verification,
- modified metadata fails signature verification,
- modified decoded payload with recomputed signature but stale hash fails hash
  verification,
- missing public key fails,
- wrong public key fails,
- fingerprint mismatch fails,
- required `ed25519` policy rejects unsigned and HMAC capsules,
- inline public key mode works when policy allows it,
- registry mode works with a local JSON registry,
- scanner reports invalid public-key capsules as high risk.

## Open Questions

- Should V1 allow inline public keys by default, or require registry mode for
  signed production channels?
- Should key IDs be free-form strings or structured URIs?
- Should key validity windows live in policy, registry entries, or both?
- Should signature timestamps be separate from `created_at`?
- Should key revocation be local-registry only for V1?
- Should optional signing extras live in this package or in a separate
  `agentcapsule-signing` package?

## Current Prototype Scope

Implemented scope:

- optional `lmcodec[signing]` dependency,
- local base64 raw Ed25519 private/public key files,
- `capsule keys generate`,
- `capsule keys fingerprint`,
- `capsule pack --sign-ed25519-key`,
- inline public key mode by default,
- registry-shaped local public key verification with `--no-inline-public-key`
  and `--ed25519-public-key`,
- local JSON trust registry verification with `--signature-registry`,
- trusted/revoked key status,
- strict tests for tampering, wrong public keys, and signature policy.

Still deferred:

- remote registry,
- time-bound validity windows,
- encrypted private keys,
- organization identity binding,
- default-install crypto dependency.

## Recommended Next Branch

`codex/agent-capsule-policy-audit-log-v0`
