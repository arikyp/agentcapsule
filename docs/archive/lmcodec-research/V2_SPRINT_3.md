# V2 Sprint 3

Sprint start: 2026-05-08

## Goal

Stress the order-3 n-gram candidate from Sprint 2.

Candidate under test:

- Model: order-3 n-gram
- Training corpus: `examples/carrier_train_v2.txt`
- Held-out corpus: `examples/carrier_heldout_v2.txt`
- Model uniform mix: `0.75`

## Questions

1. Does order 3 keep promotion checks across more than one payload?
2. Does mild runtime shaping recover enough entropy while preserving most of
   the quality gain?
3. Is order 3 strong enough to replace order 2 as the quality anchor?

## Configs

| Purpose | Config |
| --- | --- |
| Anchor payload | `experiments/configs/v2_autoagent_ngram_order3.json` |
| README payload | `experiments/configs/v2_autoagent_ngram_order3_readme.json` |
| changelog payload | `experiments/configs/v2_autoagent_ngram_order3_changelog.json` |
| mild shaping | `experiments/configs/v2_autoagent_ngram_order3_shape_u10_t115.json` |

## Comparison Anchors

- Quality baseline: `experiments/runs/v2_ngram_mixed_5k_order2/result.json`
- Safety baseline: `experiments/runs/v2_autoagent_ngram_order2_model_u85/result.json`
- Transformer anchor: `experiments/runs/v2_transformer_fixture_anchor/result.json`

## Acceptance

Sprint 3 is complete when:

- All new configs parse as JSON.
- Each new experiment writes a `result.json`.
- Results are compared with `scripts/compare_results.py`.
- One order-3 candidate report is written.
- V1 unit tests still pass.

## Results

All Sprint 3 configs parsed as JSON, ran to `result.json`, and promoted.

| Experiment | Payload bytes | Roundtrip | Promotion | Entropy | Held-out NLL | Bits/char | Carrier chars | Unique chars | Longest run | Avg top probability |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `v2-autoagent-ngram-order3` | 1128 | pass | pass | 5.582 | 3.107 | 5.988 | 1523 | 64 | 2 | 0.157 |
| `v2-autoagent-ngram-order3-changelog` | 1331 | pass | pass | 5.582 | 3.107 | 5.999 | 1791 | 64 | 2 | 0.157 |
| `v2-autoagent-ngram-order3-readme` | 9842 | pass | pass | 5.582 | 3.107 | 5.996 | 13148 | 64 | 3 | 0.157 |
| `v2-autoagent-ngram-order3-shape-u10-t115` | 1128 | pass | pass | 5.776 | 3.558 | 5.984 | 1524 | 64 | 2 | 0.109 |

Comparison anchors:

| Anchor | Entropy | Held-out NLL | Bits/char | Avg top probability |
| --- | ---: | ---: | ---: | ---: |
| order 2 quality baseline | 5.628 | 3.668 | 5.961 | 0.128 |
| order 2 safety baseline, model mix 0.85 | 5.836 | 4.178 | 5.992 | 0.083 |
| Transformer fixture anchor | 5.930 | 5.334 | 5.961 | 0.033 |

## Sprint Readout

Order 3 survived the same payload stress pattern used for order 2. It promoted
on the anchor payload, the changelog payload, and the larger README payload.

The tradeoff is now clear:

- Unshaped order 3 is the best quality candidate so far, improving held-out
  NLL by `0.561` bits against order 2.
- It is sharper than order 2: entropy is lower by `0.047` bits and top-token
  probability is higher by `0.030`.
- Mild shaping recovers entropy above the order-2 quality baseline
  (`5.776` vs `5.628`) while still beating order 2 on held-out NLL
  (`3.558` vs `3.668`).

Near-term decision:

- Promote unshaped order 3 to the current quality candidate.
- Keep shaped order 3 as the balanced candidate for the next autoagent budget.
- Do not treat order 3 as release-ready until it survives more payload sizes
  and corpus-domain variation.

## Next Lane

Sprint 4 should broaden the search space without changing the codec core:

1. Generate or reuse per-domain V2 corpora.
2. Test order 3 on `codec`, `operations`, `notes`, and `mixed` domains.
3. Add a compact candidate report for shaped order 3.
4. Keep Transformer training deferred until n-gram corpus/domain behavior is
   understood.
