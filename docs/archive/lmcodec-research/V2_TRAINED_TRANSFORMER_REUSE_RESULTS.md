# V2 Trained Transformer Reuse Results

Date: 2026-05-08

Branch: `codex/v2-transformer-trained-reuse-comparison`

Matrix:

- `experiments/matrices/v2_trained_transformer_reuse_comparison.json`
- Output: `experiments/runs/v2_trained_transformer_reuse_comparison_matrix`
- Run mode: `--timeout-seconds 120`

## Scope

This branch adds matrix-runner support for reusing one trained model per
candidate/corpus, then uses it for a bounded trained Transformer comparison.

The goal is not to beat the 1MB n-gram ceiling. The goal is to remove a runner
mechanics blocker: Transformer candidates should not retrain once per payload
cell.

Payloads:

- `binary_1kb`, `binary_10kb`
- `text_1kb`, `text_10kb`

Corpora:

- `repo_code_docs`
- `tests_protocol`

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `transformer_fixture`
- `transformer_trained_tiny`

## Runner Change

Matrix candidates can set:

```json
"reuse_model_per_corpus": true
```

For trainable `ngram` and `transformer` candidates, `scripts/run_matrix.py`
then exports one model per candidate/corpus under the matrix output directory
and points all payload configs at that model path.

Dry runs write planned config paths but do not materialize models.

## Results

The full 32-cell matrix passed hard gates.

| Candidate | Hard-gate failures | Mean NLL | Mean entropy | Mean encode seconds | Mean decode seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 0 | 4.534 | 5.888 | 0.223 | 0.130 |
| `transformer_trained_tiny` | 0 | 4.640 | 5.519 | 2.905 | 1.719 |
| `order3_balanced_shape` | 0 | 4.787 | 5.938 | 0.225 | 0.133 |
| `transformer_fixture` | 0 | 5.416 | 5.930 | 4.180 | 1.627 |

10KB-only summary:

| Candidate | Mean encode seconds | Mean decode seconds | Max encode seconds | Mean NLL | Mean entropy |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 0.378 | 0.208 | 0.392 | 4.534 | 5.888 |
| `order3_balanced_shape` | 0.379 | 0.215 | 0.394 | 4.787 | 5.938 |
| `transformer_trained_tiny` | 5.286 | 3.127 | 5.507 | 4.640 | 5.519 |
| `transformer_fixture` | 7.586 | 2.966 | 7.818 | 5.416 | 5.930 |

## Readout

The runner change works: the trained Transformer is exported once per corpus and
reused across payload cells.

The trained tiny Transformer is a real improvement over the pinned fixture:

- Better NLL: `4.640` vs `5.416`.
- Faster encode: `2.905s` vs `4.180s` mean.
- All hard gates pass after safety shaping.

It still does not beat the n-gram baselines:

- `order3_quality` has better NLL and much faster runtime.
- `order3_balanced_shape` has materially better entropy with much faster
  runtime.
- The trained Transformer's bits per carrier char are lower, reflecting the
  sharper distribution even after shaping.

## Recommendation

Keep the reusable-model runner path. It is necessary for any serious
Transformer comparison.

Do not promote `transformer_trained_tiny` as a V2 candidate. It is useful as the
first trained Transformer comparison point, but it needs better training or a
stronger architecture before larger-payload comparisons are justified.

Next Transformer work should stay at 1KB/10KB and focus on:

- training variants,
- entropy-preserving shaping,
- model quality/runtime tradeoffs,
- only promoting to 100KB after beating the fixture and approaching the n-gram
  baselines.
