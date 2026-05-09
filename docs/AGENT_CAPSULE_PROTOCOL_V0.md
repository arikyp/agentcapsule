# Agent Capsule Protocol V0

Agent Capsule Protocol V0 defines a signed-style, inspectable, verifiable text
artifact for moving exact machine-readable payloads through text-native
channels: chat, tickets, prompts, email, GitHub issues, and agent traces.

The V0 implementation uses SHA256 integrity verification and reserves explicit
metadata fields for future signing and encryption. It does not implement real
signature or encryption primitives.

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
- `codec`: payload text codec, currently `base64` or `lmcodec-fixed`.
- `content_type`: decoded payload type.
- `payload_sha256`: SHA256 of the decoded payload bytes.
- `compression`: reserved, currently `none`.
- `encryption`: reserved, currently `none`.
- `signature`: reserved, currently `none`.
- `created_by`: local producer identifier.
- `created_at`: UTC ISO timestamp.
- `policy`: policy hint, currently `inspect-before-use`.
- `filename`: optional single-file output name.

## Backend Model

V0 includes two dependency-free backends:

- `base64`: stable interoperability baseline.
- `lmcodec-fixed`: LMCodec default fixed carrier wrapped as a capsule payload
  backend.

The local codec registry is inspectable:

```bash
capsule codecs
```

Future backends can register n-gram, quality-shaped, registry-driven, or
Transformer carriers without changing the envelope model.

## Payload Formats

Single files are stored as raw decoded bytes with content type
`application/octet-stream`.

Directories are stored as deterministic JSON bundles with content type
`application/vnd.agent.bundle+json`. Bundle entries include relative path, byte
size, SHA256, and base64 file contents. Paths are sorted deterministically.

## Security Model

V0 proves the primitive, not the full security product.

- SHA256 detects payload changes relative to the capsule header.
- Metadata is readable before decode.
- Decode and unpack are separate from execution.
- Unpack verifies first and writes only under the requested output directory.
- Bundle paths are checked for absolute paths and `..` traversal.

Non-goals for V0:

- Ed25519 signing.
- Encryption or privacy.
- Remote trust registry.
- Central policy service.
- DLP or SaaS integrations.
- Runtime dependencies beyond the Python standard library and existing
  LMCodec code.

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

## Local Policy JSON

V0 supports a small local JSON policy for inspect, verify, unpack, and scan:

```json
{
  "require_known_codec": true,
  "require_hash": true,
  "allow_unsigned": true,
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
capsule scan capsule.txt --json
capsule codecs --json
```

The `--json` forms are intended for agent traces, CI checks, and governance
logs. Human-readable output remains the default.

Use the LMCodec fixed backend:

```bash
capsule pack payload.bin --codec lmcodec-fixed --out capsule.txt
capsule verify capsule.txt
```

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
