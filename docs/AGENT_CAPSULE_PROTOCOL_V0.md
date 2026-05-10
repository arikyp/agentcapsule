# Agent Capsule Protocol V0

Agent Capsule Protocol V0 defines a signed-style, inspectable, verifiable text
artifact for moving exact machine-readable payloads through text-native
channels: chat, tickets, prompts, email, GitHub issues, and agent traces.

The V0 implementation uses SHA256 integrity verification, supports optional
HMAC-SHA256 signatures for shared-secret authenticity, and has an optional
Ed25519 prototype for public-key authenticity. It reserves explicit metadata
fields for future encryption.

## Problem Statement

AI workflows commonly pass state as natural-language summaries. Summaries are
useful, but they are lossy. Enterprise and agent workflows also need exact
state: config, manifests, patches, files, tool inputs, and trace artifacts.

Agent Capsules carry both readable metadata and an exact encoded payload. A
receiver can inspect metadata first, verify the payload hash, decode into a
sandbox directory, and apply local policy before using the content.

## Envelope Format

```text
-----BEGIN AGENT CAPSULE-----
capsule_version: 0.1
codec: base64
content_type: application/vnd.agent.bundle+json
payload_sha256: <sha256>
compression: none
encryption: none
signature: none
created_by: local
created_at: <utc iso timestamp>
policy: inspect-before-use
-----PAYLOAD-----
<encoded payload>
-----END AGENT CAPSULE-----
```

The envelope is plain text and intentionally easy to find with simple scanning.
Parsers tolerate LF and CRLF line endings. Missing required headers, malformed
headers, missing boundaries, and hash mismatches are rejected.

## Metadata Fields

- `capsule_version`: protocol version, currently `0.1`.
- `codec`: payload text codec, currently `base64`, `lmcodec-fixed`, or
  `lmcodec-ngram-v2`.
- `content_type`: decoded payload type.
- `payload_sha256`: SHA256 of the decoded payload bytes.
- `compression`: reserved, currently `none`.
- `encryption`: reserved, currently `none`.
- `signature`: `none`, `hmac-sha256`, or `ed25519`.
- `signature_key_id`: optional key identifier.
- `signature_public_key_fingerprint`: SHA256 fingerprint of raw Ed25519 public
  key bytes.
- `signature_public_key_encoding`: currently `base64` when an inline Ed25519
  public key is present.
- `signature_public_key`: optional inline base64 raw Ed25519 public key.
- `signature_value_encoding`: currently `base64` for Ed25519 signatures.
- `signature_value`: HMAC-SHA256 hex digest when `signature` is `hmac-sha256`,
  or base64 Ed25519 signature when `signature` is `ed25519`.
- `created_by`: local producer identifier.
- `created_at`: UTC ISO timestamp.
- `policy`: policy hint, currently `inspect-before-use`.
- `filename`: optional single-file output name.

## Backend Model

V0 includes three dependency-free backends:

- `base64`: stable interoperability baseline.
- `lmcodec-fixed`: LMCodec default fixed carrier wrapped as a capsule payload
  backend.
- `lmcodec-ngram-v2`: LMCodec n-gram backend with explicit model metadata in
  the capsule header. V0 embeds canonical n-gram model JSON as base64 metadata
  and records model type, fingerprint, SHA256, order, and uniform mix.

The local codec registry is inspectable:

```bash
capsule codecs
```

Future backends can register n-gram, quality-shaped, registry-driven, or
Transformer carriers without changing the envelope model.

## Model Metadata Modes

`lmcodec-ngram-v2` currently uses inline model mode. The capsule embeds the
canonical n-gram model JSON in plaintext metadata as base64 and verifies it with
both SHA256 and the LMCodec model fingerprint. This is portable,
self-contained, and useful for demos, offline handoff, and exact reproduction.

Future registry model mode should replace bulky inline model metadata with a
compact model reference such as a registry ID, model fingerprint, and trust
domain. Registry mode will be more enterprise-friendly, but it requires a
trusted model registry and policy rules for which model references are allowed.

## Payload Formats

Single files are stored as raw decoded bytes with content type
`application/octet-stream`.

Directories are stored as deterministic JSON bundles with content type
`application/vnd.agent.bundle+json`. Bundle entries include relative path, byte
size, SHA256, and base64 file contents. Paths are sorted deterministically.

## Security Model

V0 proves the primitive, not the full security product.

- SHA256 detects payload changes relative to the capsule header.
- HMAC-SHA256 can authenticate a capsule when sender and receiver already share
  a secret key.
- HMAC-SHA256 does not provide public identity or non-repudiation.
- Ed25519 can verify public-key signatures when `lmcodec[signing]` is
  installed.
- Local Ed25519 registries can mark keys as trusted or revoked. They are local
  JSON files, not remote identity services.
- Metadata is readable before decode.
- Decode and unpack are separate from execution.
- Unpack verifies first and writes only under the requested output directory.
- Bundle paths are checked for absolute paths and `..` traversal.

Non-goals for V0:

- Encryption or privacy.
- Remote trust registry.
- Central policy service.
- DLP or SaaS integrations.
- Default runtime dependencies beyond the Python standard library and existing
  LMCodec code. Ed25519 is available through the optional `signing` extra.

Install the optional signing extra before running Ed25519 demos/tests:

```bash
python3 -m pip install -e ".[signing]"
```

## Decode Flow

1. Detect an Agent Capsule envelope.
2. Parse plaintext metadata.
3. Apply local metadata policy.
4. Decode payload text with the named codec.
5. Recompute SHA256 over decoded bytes.
6. Reject on mismatch.
7. Unpack into a caller-selected output directory.
8. Inspect decoded files before use.

## Scan And Governance Flow

`capsule scan <text-file>` performs lightweight governance checks:

- explicit Agent Capsule envelopes,
- malformed capsule-like blocks,
- high-entropy/base64-looking blocks,
- suspicious invisible Unicode characters,
- very long dense text blocks.

The scanner reports counts, risk level, and reasons. It is heuristic by design;
future governance layers can add policy files, allow lists, audit events, and
channel integrations.

JSON scan output also includes typed findings. Each finding carries:

- `type`: stable finding identifier such as `dense_base64_like`,
  `unicode_invisible`, `capsule_invalid`, or `capsule_malformed`.
- `risk`: `low`, `medium`, or `high`.
- `message`: human-readable finding summary.
- `line` and `column`: 1-based source location.
- `start` and `end`: character offsets in the scanned text.
- `excerpt`: capped evidence string for logs.

The scan report also includes `report_type`,
`schema_version`, `disposition`, and the effective policy. Disposition is a
simple local mapping: `low` risk allows, `medium` risk requires review, and
`high` risk blocks.

`inspect`, `verify`, `unpack`, and `scan` also support `--audit-json`, which
wraps operation results in a consistent audit event. See
[AGENT_CAPSULE_AUDIT_LOG_V0.md](AGENT_CAPSULE_AUDIT_LOG_V0.md).

## Local Policy JSON

V0 supports a small local JSON policy for inspect, verify, unpack, and scan:

```json
{
  "require_known_codec": true,
  "require_hash": true,
  "allow_unsigned": true,
  "required_signature_modes": [],
  "require_signature_registry": false,
  "allow_inline_public_keys": true,
  "trusted_signature_key_ids": [],
  "trusted_signature_key_fingerprints": [],
  "allowed_content_types": [
    "application/octet-stream",
    "application/vnd.agent.bundle+json"
  ],
  "max_payload_bytes": 1048576,
  "decode_to_sandbox_required": true
}
```

Policy files are intentionally strict about field names and types. Unknown
fields are rejected rather than ignored.

For strict public-key channels, require Ed25519 plus a local registry:

```json
{
  "allow_unsigned": false,
  "required_signature_modes": ["ed25519"],
  "require_signature_registry": true,
  "allow_inline_public_keys": false
}
```

## CLI Examples

```bash
capsule pack examples/agent_capsule_demo/handoff --out capsule.txt
capsule inspect capsule.txt
capsule verify capsule.txt
capsule unpack capsule.txt --out decoded
capsule scan capsule.txt
capsule codecs
capsule verify capsule.txt --policy examples/agent_capsule_demo/policy-strict.json
capsule inspect capsule.txt --json
capsule verify capsule.txt --audit-json
capsule scan capsule.txt --json
capsule codecs --json
sh scripts/demo_agent_capsule_governance.sh
sh scripts/demo_agent_capsule_audit.sh
```

The `--json` forms are intended for agent traces, CI checks, and governance
logs. Human-readable output remains the default.

Use the LMCodec fixed backend:

```bash
capsule pack payload.bin --codec lmcodec-fixed --out capsule.txt
capsule verify capsule.txt
```

Use the self-contained LMCodec n-gram backend:

```bash
capsule pack payload.bin \
  --codec lmcodec-ngram-v2 \
  --model tests/fixtures/ngram_model_v1.json \
  --out capsule.txt
capsule inspect capsule.txt
capsule verify capsule.txt
```

Create and verify an HMAC-signed capsule:

```bash
CAPSULE_HMAC_KEY='shared secret' \
  capsule pack payload.bin --out capsule.txt --sign-key-env CAPSULE_HMAC_KEY
CAPSULE_HMAC_KEY='shared secret' \
  capsule verify capsule.txt --key-env CAPSULE_HMAC_KEY
```

The HMAC covers all capsule headers except `signature_value` plus the encoded
payload text. Changing metadata or payload text invalidates the signature.

Create and verify an Ed25519-signed capsule:

```bash
capsule keys generate --private-key publisher.key --public-key publisher.pub
capsule pack payload.bin --out capsule.txt \
  --sign-ed25519-key publisher.key \
  --signature-key-id publisher-prod-2026q2
capsule verify capsule.txt --policy examples/agent_capsule_demo/policy-require-ed25519.json
```

By default, the Ed25519 prototype embeds the raw public key as base64 metadata
so a receiver can verify without a registry. Inline keys prove that the capsule
was signed by that key; they do not prove the key is trusted. To model registry
mode, omit inline key metadata and provide a local public key file:

```bash
capsule pack payload.bin --out capsule.txt \
  --sign-ed25519-key publisher.key \
  --signature-key-id publisher-prod-2026q2 \
  --no-inline-public-key
capsule verify capsule.txt --ed25519-public-key publisher.pub
```

Create a local registry entry:

```bash
capsule keys registry-entry \
  --key-id publisher-prod-2026q2 \
  --public-key publisher.pub \
  --publisher "Example Publisher"
```

Verify against a local registry:

```bash
capsule verify capsule.txt \
  --policy examples/agent_capsule_demo/policy-require-ed25519-registry.json \
  --signature-registry trusted-keys.json
```

The local registry format is:

```json
{
  "keys": [
    {
      "key_id": "publisher-prod-2026q2",
      "fingerprint": "<sha256>",
      "public_key": "<base64 raw Ed25519 public key>",
      "status": "trusted",
      "publisher": "Example Publisher"
    }
  ]
}
```

For the full V0 security posture, see
[AGENT_CAPSULE_THREAT_MODEL.md](AGENT_CAPSULE_THREAT_MODEL.md).
For the proposed public-key signing path, see
[AGENT_CAPSULE_ED25519_DESIGN.md](AGENT_CAPSULE_ED25519_DESIGN.md).

## Example Capsule

```text
-----BEGIN AGENT CAPSULE-----
capsule_version: 0.1
codec: base64
content_type: application/octet-stream
payload_sha256: 3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7
compression: none
encryption: none
signature: none
created_by: local
created_at: 2026-05-09T00:00:00Z
policy: inspect-before-use
filename: payload.txt
-----PAYLOAD-----
ZGF0YQ==
-----END AGENT CAPSULE-----
```
