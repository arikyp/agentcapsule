# V2 Sprint 2

Sprint start: 2026-05-08

## Goal

Make the autoagent lane useful without giving it authority over promotion.

Sprint 2 adds:

- A result comparison helper for `result.json` files.
- A candidate report template.
- A small first autoagent-style n-gram budget.

## Comparison Helper

Use:

```bash
scripts/compare_results.py \
  experiments/runs/v2_ngram_mixed_5k_order2/result.json \
  experiments/runs/v2_ngram_mixed_5k_order2_shape_u10_t115/result.json \
  experiments/runs/v2_ngram_mixed_5k_order2_shape_u20_t125/result.json \
  --baseline experiments/runs/v2_ngram_mixed_5k_order2/result.json
```

The helper prints a compact Markdown table by default and can also write
flattened JSON records for autoagent consumption:

```bash
scripts/compare_results.py experiments/runs/v2_*/result.json \
  --json-out experiments/runs/v2_comparison.json
```

## Autoagent Budget 1

The first budget is intentionally small:

| Variant | Config |
| --- | --- |
| order 3 | `experiments/configs/v2_autoagent_ngram_order3.json` |
| order 2, model mix 0.65 | `experiments/configs/v2_autoagent_ngram_order2_model_u65.json` |
| order 2, model mix 0.85 | `experiments/configs/v2_autoagent_ngram_order2_model_u85.json` |

The baseline for comparison is:

- `experiments/configs/v2_ngram_mixed_5k_order2.json`

## Rules

- The autoagent may generate configs in this style.
- Each config must write to a unique `experiments/runs/` directory.
- Each candidate needs a report based on
  `docs/V2_CANDIDATE_REPORT_TEMPLATE.md`.
- Promotion remains manual.

## Results

All three autoagent-budget configs ran to `result.json`.

Baseline:

- `v2-ngram-mixed-5k-order2`

| Experiment | Roundtrip | Promotion | Entropy | Held-out NLL | Bits/char | Carrier chars | Avg top probability | Delta NLL | Delta entropy |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `v2-autoagent-ngram-order3` | pass | pass | 5.582 | 3.107 | 5.988 | 1523 | 0.157 | -0.561 | -0.047 |
| `v2-autoagent-ngram-order2-model-u65` | pass | fail | 5.369 | 3.303 | 5.930 | 1538 | 0.172 | -0.366 | -0.260 |
| `v2-ngram-mixed-5k-order2` | pass | pass | 5.628 | 3.668 | 5.961 | 1530 | 0.128 | 0.000 | 0.000 |
| `v2-autoagent-ngram-order2-model-u85` | pass | pass | 5.836 | 4.178 | 5.992 | 1522 | 0.083 | 0.510 | 0.208 |

## Sprint Readout

The first autoagent-style budget produced three useful cases:

- `order3` is the strongest quality candidate so far. It improved held-out NLL
  by `0.561` bits and promoted, but it lowered entropy and raised top-token
  concentration.
- `order2 model_u65` improved NLL but failed promotion because entropy fell
  below the gate. This is a good reject case for the autoagent lane.
- `order2 model_u85` promoted and improved entropy and bits/char, but worsened
  held-out NLL. This is a safety-biased variant, not the quality anchor.

Near-term decision:

- Treat `order3` as the new quality candidate to stress in Sprint 3.
- Keep `order2 model_u85` as a safety candidate for higher entropy gates.
- Reject `order2 model_u65` unless a later shaped variant clears entropy
  without losing its quality gains.

## Next Lane

Sprint 3 should stress `order3` the way Sprint 1 stressed `order2`:

1. Run `order3` against `README.md` and `CHANGELOG.md`.
2. Test a mild runtime shaping variant for `order3`.
3. Compare against `order2`, `order2 model_u85`, and the Transformer fixture.
4. Write one candidate report using
   `docs/V2_CANDIDATE_REPORT_TEMPLATE.md`.
