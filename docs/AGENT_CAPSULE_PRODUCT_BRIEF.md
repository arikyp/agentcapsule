# Agent Capsule Product Brief

Agent Capsule Protocol is the product. It defines an inspectable,
verifiable artifact-transfer and governance primitive for agent and
text-native channels. Base64 is the primary V0 payload path. LMCodec is an
advanced research backend for language-model-shaped carriers, not a dependency
for normal capsule use.

## Product Thesis

AI systems operate through text, but enterprise workflows require exact state.
Natural-language summaries help humans and agents orient themselves, but they
cannot safely replace byte-exact artifacts. Agent Capsules let a sender provide
a readable handoff plus an exact encoded payload that can be inspected,
verified, decoded, and unpacked under policy.

## Primary Use Case

Exact artifact handoff through AI text channels:

- agent-to-agent handoffs,
- support tickets with attached machine-readable state,
- prompt or chat transfer of small bundles,
- GitHub issue or PR traces,
- reproducible task packets for local tools.

## Security Use Case

Agent Capsules also create a control point for governing machine-readable
payloads in text channels. A receiving system can scan for capsules and dense
payloads, require inspection before decode, enforce known codecs, verify
hashes, and unpack only into sandbox directories.

## Commercial Wedge

CapsuleGuard / AI text channel governance:

- detect exact-payload artifacts in text channels,
- distinguish declared capsules from suspicious dense text,
- enforce inspect-before-use flows,
- emit governance dispositions such as allow, review, or block,
- produce audit-friendly metadata,
- emit machine-readable JSON for governance logs and agent traces,
- emit consistent allow/review/block audit events for inspect, verify, unpack,
  and scan,
- surface typed scan findings with source location and capped evidence,
- later add signatures, registry policy, and channel integrations.

## Roadmap

Near-term protocol layers:

- backend registry for `lmcodec-ngram-v2` and quality-shaped carriers,
- JSON policy loading,
- smaller model reference modes for n-gram capsules when a local trust registry
  exists,
- public-key signed capsules with the optional Ed25519 prototype and local JSON
  trust registries; the design is tracked in
  [AGENT_CAPSULE_ED25519_DESIGN.md](AGENT_CAPSULE_ED25519_DESIGN.md),
- encrypted capsules with AES-GCM or age-style recipients,
- explicit trust registry and publisher identity,
- richer scan findings and audit JSON.

Later product layers:

- Slack, Jira, GitHub, and email integrations,
- MCP server for agent workflows,
- DLP and SIEM integrations,
- web dashboard for policy and audit review,
- Transformer capsule backend when it is practically stronger.

V0 intentionally stays small: exact artifact to inspectable text capsule,
verify, apply local policy, and unpack safely. The default path should feel
boring: Base64 payload text, SHA256, explicit metadata, optional signatures,
and sandbox unpacking.

Important distinction: a valid Ed25519 signature proves the capsule was signed
by the corresponding public key. A trusted signature means that key also passed
local registry and policy checks.

The V0 security assumptions and HMAC limits are documented in
[AGENT_CAPSULE_THREAT_MODEL.md](AGENT_CAPSULE_THREAT_MODEL.md).
