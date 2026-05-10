# Agent Capsule Audit Log V0

Agent Capsule Audit Log V0 is a structured JSON event format emitted by
`inspect`, `verify`, `unpack`, and `scan` with `--audit-json`.

The audit log is intended for CI, agent traces, ticket comments, and local
governance evidence. It does not replace capsule verification; it records the
decision and evidence produced by verification and policy checks.

## Event Shape

```json
{
  "event_type": "agent_capsule_audit",
  "schema_version": 1,
  "operation": "verify",
  "disposition": "allow",
  "subject": "capsule.txt",
  "policy": {},
  "reasons": ["operation verified successfully"],
  "result": {}
}
```

Fields:

- `event_type`: always `agent_capsule_audit`.
- `schema_version`: audit event schema version.
- `operation`: `inspect`, `verify`, `unpack`, or `scan`.
- `disposition`: `allow`, `review`, or `block`.
- `subject`: file path that was inspected, verified, unpacked, or scanned.
- `policy`: effective local policy snapshot.
- `reasons`: concise decision reasons.
- `result`: operation-specific evidence.

## Dispositions

- `allow`: verification and policy checks passed.
- `review`: content is valid but carries governance risk, such as an Ed25519
  inline key that is cryptographically valid but not trusted by a registry.
- `block`: parsing, verification, policy, registry trust, or unpack safety
  failed.

For `scan`, risk maps directly to disposition:

- `low` -> `allow`
- `medium` -> `review`
- `high` -> `block`

## Valid Signature Versus Trusted Signature

`signature_verification: ok` means the capsule text was signed by the relevant
key material.

`signature_trust.status: trusted` means the signing key also matched the local
trust registry and policy.

An inline Ed25519 public key can make a signature valid, but it is not trusted
unless local policy and registry data say so.

## Commands

```bash
capsule inspect capsule.txt --audit-json
capsule verify capsule.txt --audit-json
capsule unpack capsule.txt --out decoded --audit-json
capsule scan message.txt --audit-json
```

For registry-trusted Ed25519 capsules:

```bash
python3 -m pip install -e ".[signing]"
capsule verify capsule.txt \
  --policy examples/agent_capsule_demo/policy-require-ed25519-registry.json \
  --signature-registry trusted-keys.json \
  --audit-json
```

## Demo

```bash
PYTHON=.venv/bin/python sh scripts/demo_agent_capsule_audit.sh
```

The demo emits allow, review, and block audit events. If `cryptography` is
installed through `lmcodec[signing]`, it also emits a registry-trusted Ed25519
verification event.
