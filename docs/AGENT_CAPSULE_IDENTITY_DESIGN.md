# Agent Capsule Identity & Trust Design

This document specifies the evolution of the Agent Capsule trust system from a local static file to a more flexible identity and registry system suitable for production environments.

## Current State (V0)
- `SignatureRegistry` loads from a local JSON file.
- Keys are mapped to `key_id` and `fingerprint`.
- Policy checks if a signature status is `trusted`.
- No remote discovery, no automated revocation, no identity binding (e.g., to a domain or organization).

## Proposed Evolution: Identity Registry

### 1. Identity Binding
An "Identity" should bind a public key to an entity.
Proposed structure for a `TrustedIdentity`:

```json
{
  "identity_id": "org.example.research.agent-a",
  "display_name": "Example Research Agent A",
  "organization": "Example Org",
  "domain": "example.org",
  "public_keys": [
    {
      "key_id": "agent-a-prod-2026-01",
      "fingerprint": "...",
      "status": "trusted",
      "expires_at": "2027-01-01T00:00:00Z"
    }
  ],
  "trust_level": "high"
}
```

### 2. Multi-Source Registry
The `IdentityRegistry` should be able to load identities from:
- **Local Files:** (existing behavior)
- **Environment Variables:** For ephemeral or CI/CD trust.
- **Remote URIs:** Fetching a signed registry from a trusted source (e.g., `https://trust.example.org/capsule-keys.json`).

### 3. Key Revocation & Expiry
- Support `revoked_at` and `expires_at` fields in key entries.
- The verifier should check these against the capsule's `created_at` or the current time.

### 4. Organization Policy
Policy should be able to require identities from specific organizations or domains.

```json
{
  "allowed_organizations": ["Example Org A", "Example Org B"],
  "require_identity_match": true
}
```

## Implementation Strategy

### Phase 1: Structured Identity Registry
- Update `trust.py` to support the more structured identity format.
- Add `expires_at` validation.

### Phase 2: Remote Fetching (Deferred)
- Add support for `https://` URIs in `--signature-registry`.
- Requires a way to verify the remote registry itself (e.g., it must be signed by a bootstrap key).

### Phase 3: Identity Headers
- Add `created_by_identity` header to capsules to claim an identity ID.
- The verifier resolves this ID through the registry.

## CLI Shape

```bash
# Add a remote registry
capsule verify --signature-registry https://trust.example.com/keys.json ...

# Inspect with identity details
capsule inspect --signature-registry trusted-identities.json ...
# Output:
# Signature Identity: Example Research Agent A (org.example.research.agent-a)
# Organization: Example Org
# Trust Status: Trusted (Verified via Remote Registry)
```

## Open Questions
- Should we use DIDs (Decentralized Identifiers)?
- How to handle offline verification with remote registries (caching/TTL)?
- Should the registry itself be a capsule? (Self-hosting trust).
