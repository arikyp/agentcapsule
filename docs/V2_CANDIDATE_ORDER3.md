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
  corpus domains or larger binary payloads.

## Recommendation

Recommendation: investigate.

Rationale: order 3 is the current quality candidate, but it is not yet a
release candidate. Sprint 4 should test domain variation and compare against
the shaped order-3 safety variant before any broader promotion.
