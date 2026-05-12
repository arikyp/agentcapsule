# V2 Candidate Report: Transformer Fixture

## Candidate

- Config: `experiments/configs/v2_transformer_fixture_anchor.json`
- Output directory: `experiments/runs/v2_transformer_fixture_anchor`
- Git commit: `c4ceb9602ec8056007e39d49fcf519bcd1e3d3d5`
- Payload: `pyproject.toml`
- Payload SHA256: `bcca250c4394fc3a4f453a45ab4902e37c479767f0a48ed27c49e75dc801a4f5`
- Model type: `transformer-rf-v1`
- Model fingerprint: `cfc75d7b54524f7a09a90454d89768aa4eb75b17546607c376760e2fc9d8f851`
- Corpus: fixture model, evaluated against V2 held-out text
- Shape settings: `uniform_mix=0.8`, `temperature=1.25`

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
| Held-out NLL | 3.668 | 5.334 | 1.665 |
| Average entropy | 5.628 | 5.930 | 0.301 |
| Bits per carrier char | 5.961 | 5.961 | 0.000 |
| Carrier chars | 1530 | 1530 | 0 |
| Unique chars | 64 | 64 | 0 |
| Longest repeated run | 2 | 3 | 1 |
| Average top probability | 0.128 | 0.033 | -0.095 |

## Checkpoint Matrix

| Metric | Matrix mean |
| --- | ---: |
| Hard gate failures | 0 |
| Held-out NLL | 5.339 |
| Average entropy | 5.930 |
| Bits per carrier char | 5.896 |
| Average top probability | 0.033 |

Matrix result:

- Passed all hard gates across 12 runs.
- Ranked last by hard gates, then held-out NLL.
- Remains useful as a deterministic Transformer fixture and shaping anchor.

## Interpretation

- What improved: high entropy and very low top-token concentration.
- What regressed: held-out NLL and matrix bits per carrier character are worse
  than the n-gram candidates.
- What is uncertain: stronger Transformer training may eventually beat n-gram
  carriers, but the pinned fixture does not.

## Recommendation

Recommendation: keep as fixture anchor, reject as V2 default.

Rationale: the Transformer fixture is valuable for regression coverage and
future training comparisons, but it is not the current quality, safety, or
balanced candidate.
