# Agent Capsule Roadmap

This is the public roadmap for the current Agent Capsule direction.

## Near Term

- Keep the receiver path as the adoption wedge: `pack` on sender, `ingest` on receiver.
- Keep machine-readable governance outputs stable across CLI + SDK.
- Tighten enterprise-evaluable policy/trust visibility without adding service lock-in.

## Next

- Add environment-aware fetch policy reporting (`environment_overrides`) where
  fetch controls can be set externally.
- Expand docs for agent-to-agent, chat, ticket, and email handoff patterns with
  strict CI gate examples.
- Add more examples for verified payload delivery in structured channels.
- Tighten release process around versioning, PyPI, and changelog hygiene.

## Later

- Broader integrations for multi-agent workflows and external orchestration
  surfaces.
- Optional policy and trust extensions for production deployment patterns.
- Hosted/remote registry and dashboard ideas once the core protocol path is stable.
- Tiny JS/TS reference implementation for `pack` and `verify` to support
  browser-based agents, frontend tools, and cross-language test vectors.
