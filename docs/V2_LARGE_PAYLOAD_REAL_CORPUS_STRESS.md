# V2 Large Payload And Real-Ish Corpus Stress

Branch: `codex/v2-large-payload-and-real-corpus-stress`

## Goal

Stress the current n-gram candidates before any Transformer training work.

This branch intentionally does not:

- train a Transformer,
- change codec core semantics,
- change V1 golden fixtures,
- add runtime dependencies.

## Matrix

Spec:

- `experiments/matrices/v2_large_payload_realish.json`

Payloads:

- `binary_1kb`
- `binary_10kb`
- `binary_100kb`
- `text_1kb`
- `text_10kb`
- `text_100kb`

Corpora:

- `project_docs`: README, changelog, algorithm docs, carrier quality docs, and
  the V2 checkpoint.
- `v2_reports`: V2 sprint and candidate-report documents.

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `order2_safety_mix`

The pinned Transformer fixture is intentionally excluded. Transformer training
should wait until this stress lane clarifies n-gram behavior.

## Runtime Signal

`scripts/run_matrix.py` now records per-run `encode_seconds` and
`decode_seconds`, plus candidate-level mean runtime fields. Runtime remains a
secondary signal after hard gates and quality metrics.

## Commands

Dry run:

```bash
scripts/run_matrix.py experiments/matrices/v2_large_payload_realish.json --dry-run
```

Full matrix:

```bash
scripts/run_matrix.py experiments/matrices/v2_large_payload_realish.json
```

The full matrix is expected to be materially slower than the checkpoint matrix
because it includes 100KB payloads.

For long runs, use resume and a per-cell timeout:

```bash
scripts/run_matrix.py experiments/matrices/v2_large_payload_realish.json \
  --resume \
  --timeout-seconds 60
```

The runner prints per-cell progress and writes incremental status records to:

```text
experiments/runs/v2_large_payload_realish_matrix/matrix_progress.jsonl
```

Individual `run_experiment.py` cells may print `promotion passed: False`
because matrix cells set `run_golden_tests=false`. The matrix-level hard gate
still requires no error, roundtrip success, decoded SHA256 match, model
fingerprint stability, entropy above the configured minimum, and no convergence
failure. V1 golden safety should be verified once at branch/checkpoint level
with `sh scripts/verify_v1.sh` and `sh scripts/release_check.sh`.

## Smoke Results

Two generated configs were run to validate the matrix path before the full
100KB stress sweep:

| Config | Payload | Roundtrip | Entropy | Bits/char | Matrix hard-gate interpretation |
| --- | --- | --- | ---: | ---: | --- |
| `order3_quality` / `project_docs` | `binary_1kb` | pass | 5.932 | 5.980 | pass |
| `order3_balanced_shape` / `v2_reports` | `text_10kb` | pass | 5.959 | 6.000 | pass |

An initial full run reached the first 100KB payload and stayed CPU-bound for
more than 10 minutes in a single cell. That run was stopped and converted into
this branch-level requirement: long stress matrices need progress, resume, and
per-cell timeout controls before they are useful as routine checks.

## Capped Matrix Results

The matrix was resumed with:

```bash
scripts/run_matrix.py experiments/matrices/v2_large_payload_realish.json \
  --resume \
  --timeout-seconds 30
```

Results are summarized in:

- `docs/V2_LARGE_PAYLOAD_STRESS_RESULTS.md`

## Acceptance

The branch is useful when it can answer:

- Do all candidates survive 1KB, 10KB, and 100KB payloads?
- Does the quality/balanced order-3 decision hold on real-ish local corpora?
- Do runtime measurements expose a practical candidate preference?
- Is there any evidence that Transformer training should become the next
  priority?
