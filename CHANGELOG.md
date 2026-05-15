# Changelog

All notable changes to Agent Capsule are tracked here.

## Unreleased

- Added a stable machine-readable ingest report contract with top-level
  `report_type`, `schema_version`, `disposition`, accepted/rejected counters,
  rejected reason aggregation, and `effective_policy`.
- Added structured ingest error taxonomy fields on inline/reference results:
  `accepted`, `stage`, `reason_code`, and `reason_message`.
- Expanded reference result ergonomics with expected/actual hash fields
  (`capsule_sha256_*`, `payload_sha256_*`) while keeping `descriptor` for
  backward compatibility.
- Added `agentcapsule policy show --json` with effective policy and fetch
  defaults for governance/enterprise evaluation.
- Aligned nested ingest `scan_report` with scan CLI output by adding
  `disposition`.

## 0.1.3

- Added strict receiver ingest mode via `agentcapsule ingest --strict`
  (`--fail-on-invalid`) for CI/governance gating with non-zero exit on malformed
  or invalid/failed ingestion.
- Hardened reference ingestion by requiring and validating descriptor
  `payload_sha256`, and comparing it against fetched capsule metadata before
  unpack.
- Added default ingest `scan_report` output in `IngestResult` and JSON CLI
  output for better governance visibility.
- Removed legacy LMCodec subtree and demo handoff/dashboard surfaces to keep the
  repository focused on Agent Capsule protocol + toolkit.
- Updated README and GitHub Pages landing page with protocol-first, proof-first
  positioning around sender `pack` and receiver `ingest`.

## 0.1.0

- Initial V1 research prototype.
- Fixed 64-symbol carrier model.
- Deterministic n-gram model backend.
- Experimental deterministic Transformer-style carrier backend.
- Copy/paste armour, binary framing, CRC32 validation, model fingerprints, and
  golden fixtures.
