# V2 Transformer Comparison Results

Date: 2026-05-08

Branch: `codex/v2-transformer-comparison-against-ngram-baselines`

Matrix:

- `experiments/matrices/v2_transformer_comparison.json`
- Output: `experiments/runs/v2_transformer_comparison_matrix`
- Run mode: `--timeout-seconds 120`

## Scope

This branch compares the pinned Transformer fixture against the current n-gram
baselines after the runtime hot-path work and 1MB n-gram ceiling pass.

This comparison intentionally uses the existing fixture model:

- It avoids introducing new runtime dependencies.
- It avoids repeated per-cell Transformer training in the current matrix
  runner.
- It provides a controlled regression anchor before any heavier Transformer
  training branch.

Payloads:

- `binary_1kb`, `binary_10kb`, `binary_100kb`
- `text_1kb`, `text_10kb`, `text_100kb`

Corpora:

- `all_repo_text`
- `all_tests_protocol`

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `order2_safety_mix`
- `transformer_fixture`

## Results

The full 48-cell matrix passed hard gates.

| Candidate | Hard-gate failures | Mean NLL | Mean entropy | Mean encode seconds | Mean decode seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 0 | 4.405 | 5.866 | 1.255 | 0.659 |
| `order3_balanced_shape` | 0 | 4.678 | 5.926 | 1.304 | 0.663 |
| `order2_safety_mix` | 0 | 4.779 | 5.915 | 1.224 | 0.652 |
| `transformer_fixture` | 0 | 5.407 | 5.930 | 27.539 | 10.743 |

100KB-only summary:

| Candidate | Mean encode seconds | Mean decode seconds | Max encode seconds | Mean NLL | Mean entropy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 3.315 | 1.717 | 3.390 | 4.405 | 5.866 |
| `order3_balanced_shape` | 3.449 | 1.712 | 3.497 | 4.678 | 5.926 |
| `order2_safety_mix` | 3.149 | 1.628 | 3.377 | 4.779 | 5.915 |
| `transformer_fixture` | 74.396 | 29.014 | 74.930 | 5.407 | 5.930 |

Transformer fixture scaling:

| Payload size | Mean encode seconds | Mean decode seconds |
| --- | ---: | ---: |
| 1KB | 0.727 | 0.282 |
| 10KB | 7.494 | 2.932 |
| 100KB | 74.396 | 29.014 |

## Readout

The Transformer fixture remains useful as a deterministic regression anchor,
but it is not a competitive V2 carrier candidate.

Hard gates pass, but the fixture loses on the important comparison dimensions:

- Worse NLL than all n-gram candidates.
- Much slower encode/decode at every payload size.
- Near-best entropy, but only by a small margin over shaped order 3.

The current candidate decision still holds:

- Quality candidate: `order3_quality`
- Entropy/safety candidate: `order3_balanced_shape`
- Fallback candidate: `order2_safety_mix`
- Transformer fixture: keep as regression anchor, reject as default candidate.

## Recommendation

Do not merge the Transformer fixture as a V2 candidate replacement.

The next Transformer branch should focus on training and runner mechanics before
running larger payloads:

- Train or load each Transformer model once per corpus instead of once per
  matrix cell.
- Compare trained Transformer variants on 1KB and 10KB first.
- Promote to 100KB only if NLL and runtime beat this fixture result.
- Use the n-gram 100KB and 1MB results as the baseline to beat.
