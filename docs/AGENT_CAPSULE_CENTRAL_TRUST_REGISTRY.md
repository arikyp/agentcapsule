# Agent Capsule Central Trust Registry

The current implementation uses a local JSON signature registry. That is enough
for demos and CI, but enterprise deployments need a central trust model that is
easy to audit, cache, and reason about.

The elegant version is a signed registry snapshot model, not a mandatory online
verification service.

## Design Goals

- Keep capsule verification offline-capable.
- Make trust updates centrally governed.
- Avoid requiring every receiver to call a live service before unpacking.
- Support revocation, rotation, publisher identity, scopes, and audit history.
- Keep the local verification primitive simple: load a trusted snapshot, then
  verify capsule signatures against it.

## Registry Snapshot

A central registry should publish signed snapshots:

```json
{
  "registry_version": 1,
  "issuer": "example-enterprise-agent-trust",
  "sequence": 42,
  "created_at": "2026-05-10T00:00:00Z",
  "expires_at": "2026-05-17T00:00:00Z",
  "keys": [
    {
      "key_id": "agent-a-prod-2026q2",
      "fingerprint": "<sha256>",
      "public_key": "<base64 raw Ed25519 public key>",
      "publisher": "Agent A Production",
      "status": "trusted",
      "scopes": ["handoff:engineering", "capsule:bundle"],
      "not_before": "2026-04-01T00:00:00Z",
      "not_after": "2026-07-01T00:00:00Z"
    }
  ],
  "signature": {
    "mode": "ed25519",
    "key_id": "registry-root-2026",
    "signature": "<signature over canonical registry JSON>"
  }
}
```

Receivers cache this as a local registry file. Capsule verification remains:

```text
capsule signature valid
  + signing key present in trusted registry snapshot
  + key status/scope/time policy accepted
  = trusted capsule signature
```

## Why Snapshots

Snapshots are operationally cleaner than always-online lookup:

- CI and air-gapped receivers can verify handoffs.
- Outages in the registry service do not block every decode.
- Every decision can cite the exact registry `sequence`.
- Rollback and incident review are simple because the trust input is immutable.
- A later service can still distribute snapshots over HTTPS, S3, Git, package
  registries, MDM, or configuration management.

## Trust Chain

Suggested chain:

```text
enterprise root registry key
  -> signs registry snapshots
  -> snapshots list trusted agent/publisher keys
  -> agent keys sign capsules
  -> receiver verifies capsule under policy
```

The root registry key should be managed outside normal agent runtime. Agents
should not be able to add themselves to trust.

## Future Protocol Fields

Future capsule headers can include registry hints without making verification
depend on a network call:

```text
signature_registry_issuer: example-enterprise-agent-trust
signature_registry_sequence: 42
signature_scope: handoff:engineering
```

These are hints for policy and audit. The receiver should still use its local
trusted snapshot.

## V0 To V1 Path

1. Keep current local JSON registry for demos.
2. Add registry snapshot schema validation.
3. Add canonical registry signing and verification.
4. Add scope and validity-window policy checks.
5. Add snapshot sequence and issuer fields to audit output.
6. Add distribution adapters later.

Non-goals for the next branch:

- always-online verification service
- central dashboard
- automatic key enrollment
- remote policy execution

The next implementation branch should make local registry snapshots signed and
schema-versioned before adding any network distribution.

