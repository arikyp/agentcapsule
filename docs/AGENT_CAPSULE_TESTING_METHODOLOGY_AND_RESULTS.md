# Agent Capsule Testing Methodology And Results

Last updated: 2026-05-17

## Purpose

This document captures a practical test methodology for Agent Capsule and a baseline set of local results focused on:

- protocol correctness and safety behavior,
- edge-aware eval traceability for A-to-A handoffs,
- performance/latency behavior for chain-heavy workflows.

It complements [TESTING.md](TESTING.md), which defines the standard release verification commands.

## Methodology Overview

Testing is split into three layers.

1. Correctness and governance (core repository)
- Goal: verify deterministic behavior for parse/verify/policy/unpack/scan/reference paths.
- Source of truth: `tests/` and `scripts/release_check.sh`.
- Pass criteria: all unit tests pass, compile checks pass, release check passes.

2. Handoff eval traceability (external eval layer)
- Goal: convert ingest evidence into structured handoff eval events with deterministic scores.
- Workspace: `/home/ubuntu/code/capsule-eval`.
- Coverage: valid, tampered, malformed, blocked, skipped, and downstream-success/failure/compliance cases.

3. Performance and latency (external benchmark harness)
- Goal: quantify overhead by operation and identify regression risk in larger A-to-A chains.
- Workspace: `/home/ubuntu/code/capsule-perf-bench`.
- Coverage: `pack`, `verify`, `unpack`, `ingest`, `scan`, malformed input, policy-block path.

## Reproducibility Commands

Core repository:

```bash
python3 -m pip install -e .
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m compileall src scripts tests
sh scripts/release_check.sh
```

Eval traceability:

```bash
cd /home/ubuntu/code/capsule-eval
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src python3 examples/agent_evals_traceability/run_demo.py
```

Performance benchmark:

```bash
cd /home/ubuntu/code/capsule-perf-bench
PYTHONPATH=/home/ubuntu/code/agentcapsule/src python3 scripts/run_bench.py \
  --matrix experiments/latency_matrix.json \
  --output output/benchmark_results.json
```

## Results Snapshot

### A) Core correctness and governance

- Core validation commands completed successfully in this environment.
- Receiver/governance behavior remains deterministic for:
  - malformed capsule boundary detection,
  - payload hash mismatch blocking,
  - policy-block path with stable reason codes,
  - reference descriptor mismatch handling.

### B) Edge-aware handoff eval (A-to-A demo)

Source: `/home/ubuntu/code/capsule-eval/examples/agent_evals_traceability/output/handoff_eval_summary.json`

- Events: `1`
- Disposition: `allow=1`, `review=0`, `block=0`
- Scores:
  - `handoff_integrity=1.0`
  - `handoff_completeness=1.0`
  - `receiver_compliance=1.0`
  - `downstream_utility=1.0`
  - `overall=1.0`

Interpretation:
- The sample planner->builder handoff was complete, exact, policy-compliant, safely consumed, and successful downstream.

### C) Performance benchmark (latency matrix v1)

Source: `/home/ubuntu/code/capsule-perf-bench/output/benchmark_results.json`

Run scope:
- 12 experiments across pack/verify/unpack/ingest/scan/blocked paths.

Selected headline numbers:
- slowest: `ingest_inline_one_capsule_1mb` mean `~174.5 ms` (p95 `~221.6 ms`)
- fastest: `ingest_malformed_inline_block` mean `~0.245 ms`
- avg mean latency by operation:
  - `pack ~4.26 ms`
  - `verify ~12.61 ms`
  - `unpack ~14.24 ms`
  - `ingest ~76.78 ms`
  - `scan ~96.86 ms`
  - `ingest_policy_block ~24.97 ms`

Interpretation for large A-to-A chains:
- per-edge overhead is additive, so chain latency scales with number of handoffs.
- larger payloads and repeated inline capsules increase ingest/scan cost.
- policy-block paths are significantly cheaper than full successful ingest for large payloads.

## How To Use These Results

- Use this snapshot as a baseline, not a universal constant.
- Track p95 and mean by operation over time; compare against baseline files.
- For chain-heavy workflows, report:
  - per-edge p95,
  - cumulative chain latency,
  - payload-size normalized overhead (ms/MB),
  - safety outcomes (block/review reason-code distribution).

## Limitations

- Results are environment-dependent (CPU, filesystem, Python/runtime versions).
- The benchmark matrix currently focuses on local/offline scenarios (no network fetch latency).
- Optional extras (`signing`, `compression`, `fetch`) should be benchmarked separately if used in production.

## Next Iteration

- Add matrix variants for signed capsules and trust-registry checks.
- Add bundle depth/path-count stress cases.
- Add nightly baseline comparison in CI with regression thresholds.
- Add chain simulator mode (`N` sequential handoffs) to model cumulative A-to-A latency directly.
