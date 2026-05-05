# Changelog

All notable changes to LMCodec are tracked here.

## Unreleased

- Added GitHub Actions CI for Python 3.11, 3.12, and 3.13.
- Added benchmark JSON output for comparison and shaping sweep scripts.
- Added a documented benchmark JSON schema contract at
  `schemas/benchmark_result_v1.json`.
- Added a bounded V2 experiment runner with reproducible artifacts.
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
