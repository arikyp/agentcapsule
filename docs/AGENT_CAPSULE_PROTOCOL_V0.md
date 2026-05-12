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

## Public Spec Orientation

Agent Capsule is the format. Base64 is the primary V0 payload text codec.
LMCodec backends are optional advanced/research codecs for carrier-shaping
experiments. A conforming V0 receiver should implement the Base64 capsule path
first: parse the envelope, inspect metadata, verify SHA256, apply local policy,
decode the payload, and unpack only into a caller-selected sandbox directory.

## Envelope Vs Manifest Vs Delivery Mode

These terms are separate on purpose:

- Envelope: the outer text artifact with boundary markers, protocol headers,
  encoded payload text, payload hash, signature metadata, and codec selection.
- Manifest: a canonical JSON header inside the envelope. It describes handoff
  intent, producer, task id, decoded file inventory, requested receiver
  capabilities, policy hints, and delivery metadata.
- Delivery mode: a manifest claim about how the capsule reaches the receiver:
  inline body text, attached file/blob, or reference descriptor plus URI.

The envelope is what gets parsed and signed. The manifest is what gets
inspected before decode. The delivery mode tells the receiving channel where
the envelope bytes are expected to appear.

## Relationship To MCP / A2A / ACP / MIME / IPFS

Agent Capsule is not a replacement for agent protocols, transport protocols, or
storage systems. It is a portable artifact format that can travel through them.

- MCP: an MCP tool or resource can produce, receive, inspect, verify, or unpack
  a capsule. The capsule is the artifact; MCP is one possible tool interface.
- A2A: an agent-to-agent message can carry an inline capsule, attach a capsule
  file/blob, or carry a reference descriptor.
- ACP-style agent protocols: Agent Capsule provides the byte-exact handoff
  artifact and verification rules that an agent communication protocol can
  embed or reference.
- MIME/email: a capsule can be pasted into a text part or attached as a
  `text/plain` or application-specific blob.
- GitHub/issues/PRs: a capsule can appear inline in a comment, as an uploaded
  artifact, or as a reference descriptor in an audit trail.
- IPFS/object stores/S3-like storage: a reference descriptor can point to
  content-addressed or location-addressed storage, but receivers still verify
  `capsule_sha256`, payload SHA256, and signatures from the fetched capsule.

## Envelope Format

```text
-----BEGIN AGENT CAPSULE-----
capsule_version: 0.1
codec: base64
content_type: application/vnd.agent.bundle+json
capsule_manifest: {"capsule_type":"agent_handoff","created_by":"agent-a","delivery":{"mode":"inline"},"files":[{"bytes":1204,"path":"patch.diff","sha256":"<sha256>"}],"policy_hints":{"network_egress":false,"sandbox_required":true},"requested_capabilities":["read_files","run_tests"],"task_id":"abc123"}
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
- `capsule_manifest`: optional canonical JSON manifest for agent handoff
  intent, delivery mode, file inventory, requested receiver capabilities, and
  policy hints.
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

## Capsule Manifest

Newly built capsules include a canonical JSON `capsule_manifest` header. The
header is inspectable before payload decode and is covered by HMAC-SHA256 or
Ed25519 signatures when the capsule is signed.

```json
{
  "capsule_type": "agent_handoff",
  "created_by": "agent-a",
  "task_id": "abc123",
  "delivery": {
    "mode": "inline"
  },
  "files": [
    {
      "path": "patch.diff",
      "sha256": "<sha256>",
      "bytes": 1204
    }
  ],
  "requested_capabilities": ["read_files", "run_tests"],
  "policy_hints": {
    "sandbox_required": true,
    "network_egress": false
  }
}
```

The `files` list describes decoded files by relative path, SHA256, and byte
length. For directory bundles, this inventory mirrors the bundle file entries
without embedding file contents in the header. Receivers should treat
`requested_capabilities` and `policy_hints` as claims to evaluate against local
policy, not as authorization by themselves.

## Delivery Modes

V0 distinguishes three delivery modes:

1. `inline`: the complete capsule envelope is pasted directly into the message
   body.
2. `attachment`: the complete capsule envelope is attached as a file or blob to
   A2A, MIME, GitHub, or a similar channel.
3. `reference`: the message carries a reference descriptor with a capsule URI,
   capsule SHA256, payload SHA256, and signature metadata. The receiver fetches
   the full capsule, verifies the referenced capsule hash, then performs normal
   capsule verification.

`inline` and `attachment` use the same capsule envelope bytes. They differ only
in channel handling and in the manifest `delivery.mode` claim. `reference`
still requires the full capsule to exist at the referenced URI; the URI is only
a locator and does not replace hash or signature verification.

A compact reference descriptor has this shape:

```json
{
  "reference_type": "agent_capsule_reference",
  "schema_version": 1,
  "capsule_uri": "https://example.test/capsules/abc.txt",
  "capsule_sha256": "<sha256 of full capsule envelope bytes>",
  "payload_sha256": "<sha256 of decoded payload bytes>",
  "signature": {
    "mode": "ed25519",
    "key_id": "agent-a-demo-2026q2",
    "public_key_fingerprint": "<sha256>"
  }
}
```

The reference descriptor is not authoritative. Receivers must fetch the full
capsule, verify `capsule_sha256` over the fetched envelope bytes, then verify
the capsule payload hash and signature from the fetched capsule. Signature
fields in the descriptor are hints for routing, trust lookup, and preflight
display only.

The local CLI can emit this descriptor:

```bash
capsule reference agent-a-handoff.capsule.txt \
  --uri https://example.test/capsules/agent-a-handoff.capsule.txt \
  --json
```

## Backend Model

V0 includes one primary backend plus two advanced LMCodec research backends:

- `base64`: stable interoperability baseline and recommended default.
- `lmcodec-fixed`: advanced LMCodec fixed carrier wrapped as a capsule payload
  backend for deterministic carrier-shaping experiments.
- `lmcodec-ngram-v2`: advanced LMCodec n-gram backend with explicit model
  metadata in the capsule header. V0 embeds canonical n-gram model JSON as
  base64 metadata and records model type, fingerprint, SHA256, order, and
  uniform mix.

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
The capsule manifest repeats the relative path, SHA256, and byte count so a
receiver can inspect handoff scope before decoding the payload.

## Size Guidance

V0 is optimized for small to medium handoff artifacts, not bulk data transfer.

- Inline capsules: best for small payloads that humans or agents can tolerate
  in a message body. Keep inline capsules small enough for the target channel's
  message, token, and moderation limits.
- Attachment capsules: preferred for larger bundles that still need to travel
  with the message. Receivers should enforce local `max_payload_bytes` policy.
- Reference descriptors: preferred when capsule bytes should live in object
  storage, a repository artifact, IPFS, or another durable location. The
  descriptor must include a capsule hash; the fetched capsule remains
  authoritative.
- Large files: do not inline raw large files. Store large data externally and
  use the capsule for manifests, patches, task state, checksums, and policy
  evidence.

Base64 expands payload bytes by about one third before envelope overhead.
Directory bundles add JSON field names plus per-file base64 content. LMCodec
research carriers are generally larger and slower than Base64; use them only
when carrier-shaping is the experiment.

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

Base64 is the primary V0 path:

```bash
agentcapsule pack payload.bin --out capsule.txt
agentcapsule inspect capsule.txt
agentcapsule verify capsule.txt
agentcapsule unpack capsule.txt --out decoded
```

Pack a directory handoff with manifest metadata:

```bash
agentcapsule pack examples/agent_capsule_demo/handoff \
  --out capsule.txt \
  --created-by agent-a \
  --task-id abc123 \
  --requested-capability read_files \
  --requested-capability run_tests \
  --policy-hint sandbox_required=true \
  --policy-hint network_egress=false
agentcapsule scan capsule.txt
```

Emit machine-readable output for agents and governance logs:

```bash
agentcapsule codecs
agentcapsule verify capsule.txt --policy examples/agent_capsule_demo/policy-strict.json
agentcapsule inspect capsule.txt --json
agentcapsule verify capsule.txt --audit-json
agentcapsule scan capsule.txt --json
agentcapsule codecs --json
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
  agentcapsule pack payload.bin --out capsule.txt --sign-key-env CAPSULE_HMAC_KEY
CAPSULE_HMAC_KEY='shared secret' \
  agentcapsule verify capsule.txt --key-env CAPSULE_HMAC_KEY
```

The HMAC covers all capsule headers except `signature_value` plus the encoded
payload text. Changing metadata or payload text invalidates the signature.

Create and verify an Ed25519-signed capsule:

```bash
agentcapsule keys generate --private-key publisher.key --public-key publisher.pub
agentcapsule pack payload.bin --out capsule.txt \
  --sign-ed25519-key publisher.key \
  --signature-key-id publisher-prod-2026q2
agentcapsule verify capsule.txt --policy examples/agent_capsule_demo/policy-require-ed25519.json
```

By default, the Ed25519 prototype embeds the raw public key as base64 metadata
so a receiver can verify without a registry. Inline keys prove that the capsule
was signed by that key; they do not prove the key is trusted. To model registry
mode, omit inline key metadata and provide a local public key file:

```bash
agentcapsule pack payload.bin --out capsule.txt \
  --sign-ed25519-key publisher.key \
  --signature-key-id publisher-prod-2026q2 \
  --no-inline-public-key
agentcapsule verify capsule.txt --ed25519-public-key publisher.pub
```

Create a local registry entry:

```bash
agentcapsule keys registry-entry \
  --key-id publisher-prod-2026q2 \
  --public-key publisher.pub \
  --publisher "Example Publisher"
```

Verify against a local registry:

```bash
agentcapsule verify capsule.txt \
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

## Developer Quickstart

For local development:

```bash
python3 -m pip install -e .
printf 'agent handoff state\n' > payload.txt
agentcapsule pack payload.txt --out capsule.txt
agentcapsule inspect capsule.txt --json
agentcapsule verify capsule.txt
agentcapsule unpack capsule.txt --out decoded
cmp payload.txt decoded/payload.txt
```

For signed local testing:

```bash
CAPSULE_HMAC_KEY='shared secret' agentcapsule pack payload.txt \
  --out signed.capsule.txt \
  --sign-key-env CAPSULE_HMAC_KEY \
  --signature-key-id dev-shared-key
CAPSULE_HMAC_KEY='shared secret' agentcapsule verify signed.capsule.txt --key-env CAPSULE_HMAC_KEY
```

For reference-mode testing:

```bash
agentcapsule pack payload.txt \
  --out reference.capsule.txt \
  --delivery-mode reference \
  --delivery-uri https://example.test/capsules/reference.capsule.txt
agentcapsule reference reference.capsule.txt \
  --uri https://example.test/capsules/reference.capsule.txt \
  --json
```

## Objection Handling

Why not just Base64?

Base64 is the default capsule codec. Agent Capsule adds the missing operating
contract around it: inspectable metadata, payload hash, optional signatures,
manifest file inventory, delivery mode, local policy, audit events, and safe
unpack semantics.

Why not just MCP?

MCP defines a tool/resource interface. It does not by itself define a portable,
signed, byte-exact artifact format that can also survive email, GitHub, tickets,
or other text channels. MCP can carry Agent Capsules.

Why not just S3 or another object store?

Object stores solve location and durability. They do not provide a standard
agent handoff envelope, manifest, local policy flow, or channel-independent
audit evidence. Reference delivery can point to object storage while still
requiring capsule hash and signature verification.

Why not just a Git patch?

Git patches are excellent for source changes. Agent Capsules can carry patches,
but also configs, task state, tool inputs, multi-file bundles, policy hints, and
signature/trust metadata. Capsules are a general handoff container, not a patch
format replacement.

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
capsule_manifest: {"capsule_type":"agent_handoff","created_by":"local","delivery":{"mode":"inline"},"files":[{"bytes":4,"path":"payload.txt","sha256":"3a6eb0790f39ac87c94f3856b2dd2c5d110e6811602261a9a923d3bb23adc8b7"}],"policy_hints":{"network_egress":false,"sandbox_required":true},"requested_capabilities":[],"task_id":""}
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
