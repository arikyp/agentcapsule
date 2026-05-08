# V2 Candidate Report: Order-3 N-Gram

## Candidate

- Config: `experiments/configs/v2_autoagent_ngram_order3.json`
- Output directory: `experiments/runs/v2_autoagent_ngram_order3`
- Git commit: `c4ceb9602ec8056007e39d49fcf519bcd1e3d3d5`
- Payload: `pyproject.toml`
- Payload SHA256: `bcca250c4394fc3a4f453a45ab4902e37c479767f0a48ed27c49e75dc801a4f5`
- Model type: `ngram-v1`
- Model fingerprint: `aba0d97e81ebf6781edebf4bae4581ad39e97c744de69e563ac20b7892900c22`
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

| Metric | Baseline | Candidate | Delta |
| --- | ---: | ---: | ---: |
| Held-out NLL | 3.668 | 3.107 | -0.561 |
| Average entropy | 5.628 | 5.582 | -0.047 |
| Bits per carrier char | 5.961 | 5.988 | 0.027 |
| Carrier chars | 1530 | 1523 | -7 |
| Unique chars | 64 | 64 | 0 |
| Longest repeated run | 2 | 2 | 0 |
| Average top probability | 0.128 | 0.157 | 0.030 |

## Interpretation

- What improved: held-out NLL, carrier length, and bits per carrier character
  improved against the order-2 quality baseline.
- What regressed: entropy dropped slightly and top-token concentration rose,
  so the model is sharper.
- What is uncertain: this candidate has not yet been tested across independent
  larger binary payloads.

## Checkpoint Matrix

The V2 checkpoint matrix tested this candidate across three deterministic
payloads and three deterministic corpus domains.

| Metric | Matrix mean |
| --- | ---: |
| Hard gate failures | 0 |
| Held-out NLL | 4.450 |
| Average entropy | 5.904 |
| Bits per carrier char | 5.924 |
| Average top probability | 0.064 |

Matrix result:

- Passed all hard gates across 12 runs.
- Ranked first by hard gates, then held-out NLL.
- Still sharper than the shaped order-3 candidate.

## Recommendation

Recommendation: promote as quality candidate.

Rationale: order 3 is the current quality candidate after Sprint 3 and the
checkpoint matrix. It should be promoted as the V2 quality baseline, not as a
runtime default or format change.
