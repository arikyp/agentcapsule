# V2 Candidate Report: Order-2 Safety Mix

## Candidate

- Config: `experiments/configs/v2_autoagent_ngram_order2_model_u85.json`
- Output directory: `experiments/runs/v2_autoagent_ngram_order2_model_u85`
- Git commit: `c4ceb9602ec8056007e39d49fcf519bcd1e3d3d5`
- Payload: `pyproject.toml`
- Payload SHA256: `bcca250c4394fc3a4f453a45ab4902e37c479767f0a48ed27c49e75dc801a4f5`
- Model type: `ngram-v1`
- Model fingerprint: `b0ac64943c149f489dbceba6cb1020a8cdb6731a306403db6a7478bdabe765d1`
- Corpus: `examples/carrier_train_v2.txt`
- Shape settings: no runtime shaping

## Promotion

- Promotion passed: true
- Roundtrip success: true
- Decoded SHA256 matches: true
- Model fingerprint stable: true
- Entropy above minimum: true
- Convergence failures: 0
- Golden tests unaffected: true

## Metrics

Baseline is unshaped order 2 with model uniform mix `0.75`.

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Held-out NLL | 3.668 | 4.178 | 0.510 |
| Average entropy | 5.628 | 5.836 | 0.208 |
| Bits per carrier char | 5.961 | 5.992 | 0.031 |
| Carrier chars | 1530 | 1522 | -8 |
| Unique chars | 64 | 64 | 0 |
| Longest repeated run | 2 | 3 | 1 |
| Average top probability | 0.128 | 0.083 | -0.045 |

## Checkpoint Matrix

| Metric | Matrix mean |
| --- | ---: |
| Hard gate failures | 0 |
| Held-out NLL | 4.744 |
| Average entropy | 5.931 |
| Bits per carrier char | 5.811 |
| Average top probability | 0.054 |

Matrix result:

- Passed all hard gates across 12 runs.
- Ranked third by hard gates, then held-out NLL.

## Interpretation

- What improved: entropy and top-token concentration improved against the
  order-2 quality baseline.
- What regressed: held-out NLL is materially worse than both order-3
  candidates.
- What is uncertain: it may still be useful as an efficiency fallback, but it
  no longer appears to be the best safety candidate.

## Recommendation

Recommendation: demote.

Rationale: order-2 safety mix still passes gates, but shaped order 3 has
better entropy, top-token concentration, and held-out quality in the checkpoint
matrix.
