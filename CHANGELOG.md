# Changelog

All notable changes to Agent Capsule are tracked here.

## Unreleased

- Clarified the public docs versioning so `V0` is the protocol label and
  `V1` survives only as legacy fixture and verification terminology.
- Bumped the package version to `0.1.1` for the next release.
- Added GitHub Actions CI for Python 3.11, 3.12, and 3.13.
- Added benchmark JSON output for comparison and shaping sweep scripts.
- Added a documented benchmark JSON schema contract at
  `schemas/benchmark_result_v1.json`.
- Added a bounded V2 experiment runner with reproducible artifacts.
- Added V2 baseline, experiment protocol, autoagent guardrail docs, and initial
  V2 fixed, n-gram, and Transformer anchor configs.
- Added the first V2 sprint plan and bounded n-gram order-2 stress configs.
- Added a result comparison helper, candidate report template, and first
  autoagent-safe n-gram budget configs.
- Added the third V2 sprint plan, order-3 stress configs, and an order-3
  candidate report.
- Added deterministic V2 payload and matrix specs, a matrix runner, checkpoint
  candidate reports, and a V2 research checkpoint.
- Added the next V2 stress-lane matrix for larger payloads, real-ish local
  corpora, and runtime signals.
- Added capped large-payload stress results showing the current 100KB runtime
  boundary.
- Added a scaled V2 size-ladder matrix for 16KB, 32KB, and 64KB payloads.
- Added partial size-ladder results identifying 32KB as the current routine
  stress ceiling before runtime profiling.
- Added a profiling helper for single experiment configs.
- Added carrier quality metrics and corpus report utilities.
- Added stress tests for roundtrip, range coder, quantizer, and corruption
  handling.
- Reworked README and added algorithm, benchmarking, experiments, carrier
  quality, testing, and baseline documentation.

## 0.1.0

- Initial V1 research prototype.
- Fixed 64-symbol carrier model.
- Deterministic n-gram model backend.
- Experimental deterministic Transformer-style carrier backend.
- Copy/paste armour, binary framing, CRC32 validation, model fingerprints, and
  golden fixtures.
