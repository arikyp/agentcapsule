# V2 Candidate Report: Shaped Order-3 N-Gram

## Candidate

- Config: `experiments/configs/v2_autoagent_ngram_order3_shape_u10_t115.json`
- Output directory: `experiments/runs/v2_autoagent_ngram_order3_shape_u10_t115`
- Git commit: `c4ceb9602ec8056007e39d49fcf519bcd1e3d3d5`
- Payload: `pyproject.toml`
- Payload SHA256: `bcca250c4394fc3a4f453a45ab4902e37c479767f0a48ed27c49e75dc801a4f5`
- Model type: `ngram-v1`
- Model fingerprint: `aba0d97e81ebf6781edebf4bae4581ad39e97c744de69e563ac20b7892900c22`
- Corpus: `examples/carrier_train_v2.txt`
- Shape settings: `uniform_mix=0.1`, `temperature=1.15`

## Promotion

- Promotion passed: true
- Roundtrip success: true
- Decoded SHA256 matches: true
- Model fingerprint stable: true
- Entropy above minimum: true
- Convergence failures: 0
- Golden tests unaffected: true

## Metrics

Baseline is unshaped order 2.

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Held-out NLL | 3.668 | 3.558 | -0.110 |
| Average entropy | 5.628 | 5.776 | 0.148 |
| Bits per carrier char | 5.961 | 5.984 | 0.023 |
| Carrier chars | 1530 | 1524 | -6 |
| Unique chars | 64 | 64 | 0 |
| Longest repeated run | 2 | 2 | 0 |
| Average top probability | 0.128 | 0.109 | -0.019 |

## Checkpoint Matrix

| Metric | Matrix mean |
| --- | ---: |
| Hard gate failures | 0 |
| Held-out NLL | 4.722 |
| Average entropy | 5.948 |
| Bits per carrier char | 5.868 |
| Average top probability | 0.049 |

Matrix result:

- Passed all hard gates across 12 runs.
- Ranked second by hard gates, then held-out NLL.
- Had the highest mean entropy among checkpoint candidates.

## Interpretation

- What improved: better entropy and lower top-token concentration than
  unshaped order 3 while still beating order 2 on quality.
- What regressed: held-out NLL is worse than unshaped order 3.
- What is uncertain: whether this should replace unshaped order 3 depends on
  the chosen balance between naturalness and entropy margin.

## Recommendation

Recommendation: promote as balanced candidate.

Rationale: shaped order 3 is the strongest all-around candidate. It gives up
some quality against unshaped order 3, but it improves entropy and remains
well ahead of the Transformer fixture.
