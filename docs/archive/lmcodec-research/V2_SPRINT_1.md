# V2 Sprint 1

Sprint start: 2026-05-08

## Goal

Stress the first promising V2 carrier candidate before moving to Transformer
training or autoagent-driven sweeps.

Candidate under test:

- Model: order-2 n-gram
- Training corpus: `examples/carrier_train_v2.txt`
- Held-out corpus: `examples/carrier_heldout_v2.txt`
- Model uniform mix: `0.75`

## Questions

1. Does the order-2 n-gram candidate keep promotion checks across more than
   one payload?
2. Does mild runtime shaping improve entropy safety without destroying held-out
   quality?
3. Is the candidate stable enough to become the near-term baseline for the
   autoagent search lane?

## Configs

| Purpose | Config |
| --- | --- |
| Anchor payload | `experiments/configs/v2_ngram_mixed_5k_order2.json` |
| README payload | `experiments/configs/v2_ngram_mixed_5k_order2_readme.json` |
| changelog payload | `experiments/configs/v2_ngram_mixed_5k_order2_changelog.json` |
| mild shaping | `experiments/configs/v2_ngram_mixed_5k_order2_shape_u10_t115.json` |
| stronger shaping | `experiments/configs/v2_ngram_mixed_5k_order2_shape_u20_t125.json` |

## Acceptance

Sprint 1 is complete when:

- All configs parse as JSON.
- Each experiment has a generated `result.json`.
- Passing/failing promotion status is recorded here.
- V1 unit tests still pass.
- The next experiment lane is clear.

## Results

All Sprint 1 configs parsed as JSON and produced `result.json` artifacts.

| Experiment | Payload bytes | Roundtrip | Promotion | Entropy | Held-out NLL | Bits/char | Carrier chars | Unique chars | Longest run | Avg top probability |
| --- | ---: | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `v2-ngram-mixed-5k-order2` | 1128 | pass | pass | 5.628 | 3.668 | 5.961 | 1530 | 64 | 2 | 0.128 |
| `v2-ngram-mixed-5k-order2-changelog` | 1125 | pass | pass | 5.628 | 3.668 | 5.969 | 1524 | 64 | 3 | 0.128 |
| `v2-ngram-mixed-5k-order2-readme` | 9452 | pass | pass | 5.628 | 3.668 | 5.971 | 12679 | 64 | 3 | 0.128 |
| `v2-ngram-mixed-5k-order2-shape-u10-t115` | 1128 | pass | pass | 5.796 | 4.038 | 5.976 | 1526 | 64 | 2 | 0.091 |
| `v2-ngram-mixed-5k-order2-shape-u20-t125` | 1128 | pass | pass | 5.869 | 4.293 | 5.976 | 1526 | 64 | 3 | 0.072 |

## Sprint Readout

The unshaped order-2 candidate survived the first payload stress pass. It
promoted on the original `pyproject.toml` payload, the similar-sized changelog
payload, and the larger README payload.

Runtime shaping behaved as expected:

- Mild shaping raised entropy from `5.628` to `5.796`.
- Stronger shaping raised entropy to `5.869`.
- Both shaping variants reduced top-token concentration.
- Both shaping variants worsened held-out NLL, from `3.668` to `4.038` and
  `4.293`.

Near-term decision:

- Keep unshaped order 2 as the current quality anchor.
- Keep shaped order 2 as the safety anchor when a higher entropy floor is
  needed.
- Do not promote shaped variants as the default unless later payload stress
  shows the unshaped candidate is too sharp.

## Next Lane

Sprint 2 should make the autoagent useful without giving it promotion control:

1. Add a compact result-comparison helper or documented `jq` recipe.
2. Add an autoagent-readable candidate report template.
3. Let the autoagent vary n-gram order, model uniform mix, runtime shaping, and
   corpus domain within a small budget.
4. Require each proposed winner to pass the same promotion gates and be written
   up before manual review.

## Autoagent Note

If the order-2 candidate survives this sprint, it is a good first autoagent
target. The autoagent can vary n-gram order, model uniform mix, runtime
shaping, payload, and corpus domain under the protocol in
`docs/V2_AUTOAGENT.md`.
