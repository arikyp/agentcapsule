# LMCodec V2 Research Checkpoint

Date: 2026-05-08

V2 is now a promotion-grade research checkpoint. It is not a codec format
release and does not change V1 semantics.

## Preserved V1 Guarantees

No codec core semantics changed in this checkpoint:

- No frame or armour behavior changes.
- No golden fixture changes.
- No range coder, quantizer, codec, or model runtime dependency changes.
- No new runtime dependencies.

Verification:

- `sh scripts/verify_v1.sh`: passed, 69 tests.
- `sh scripts/release_check.sh`: passed, 69 tests.

The V2 matrix runs did not repeat golden tests in every cell. Instead, V1
golden safety was verified once at checkpoint level, and each matrix cell used
hard transport gates.

## Tooling Added

- `scripts/compare_results.py`: compares result JSON files and reports
  baseline deltas.
- `scripts/run_matrix.py`: materializes deterministic payloads and corpus
  splits, runs a bounded experiment matrix, and ranks candidates.
- `experiments/payload_suite_v1.json`: deterministic payload-suite manifest.
- `experiments/matrices/v2_checkpoint.json`: checkpoint matrix spec.

## Checkpoint Matrix

The checkpoint matrix tested four candidates across four deterministic
payloads and three deterministic corpus domains.

Payloads:

| Payload | Bytes | SHA256 |
| --- | ---: | --- |
| `empty` | 0 | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| `tiny_text` | 30 | `46d853f012dcb5ef3540947b1d2639defc364a1cf4d09997832186ccecc38d58` |
| `structured_json` | 98 | `6a5b6e9155264fc5127465b1d8626817e648a804d654222bdf0dfef8af59ea82` |
| `binary_256` | 256 | `40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880` |

Corpus domains:

- `codec`
- `notes`
- `mixed`

Hard gates:

- no error
- roundtrip success
- decoded SHA256 matches payload SHA256
- model fingerprint stability
- entropy above configured minimum
- no convergence failure

All 48 matrix runs passed hard gates.

## Candidate Ranking

Matrix ranking uses hard gates first and held-out NLL second.

| Rank | Candidate | Hard gate failures | Mean NLL | Mean entropy | Mean bits/char | Mean top probability |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 1 | `order3_quality` | 0 | 4.450 | 5.904 | 5.924 | 0.064 |
| 2 | `order3_balanced_shape` | 0 | 4.722 | 5.948 | 5.868 | 0.049 |
| 3 | `order2_safety_mix` | 0 | 4.744 | 5.931 | 5.811 | 0.054 |
| 4 | `transformer_fixture` | 0 | 5.339 | 5.930 | 5.896 | 0.033 |

## Current Candidates

Quality candidate:

- `order3_quality`
- Best mean held-out NLL in the checkpoint matrix.
- Slightly sharper than shaped order 3.
- Candidate report: `docs/V2_CANDIDATE_ORDER3.md`.

Safety and balanced candidate:

- `order3_balanced_shape`
- Best combined quality and entropy profile.
- Highest mean entropy among checkpoint candidates while keeping strong NLL.
- Candidate report: `docs/V2_CANDIDATE_ORDER3_SHAPED.md`.

Demoted safety fallback:

- `order2_safety_mix`
- Passes all hard gates.
- No longer the strongest safety candidate because shaped order 3 has better
  entropy, top-token concentration, and NLL in the checkpoint matrix.
- Candidate report: `docs/V2_CANDIDATE_ORDER2_SAFETY.md`.

Fixture anchor:

- `transformer_fixture`
- Passes all hard gates and remains useful for regression and future
  Transformer training comparisons.
- Not a V2 default candidate because held-out NLL and matrix bits/char are
  worse than n-gram candidates.
- Candidate report: `docs/V2_CANDIDATE_TRANSFORMER_FIXTURE.md`.

## Rejected Or Demoted Options

- `v2-autoagent-ngram-order2-model-u65`: rejected because it roundtripped but
  failed the entropy promotion gate.
- Transformer fixture as V2 default: rejected for current default promotion
  because it ranks last by held-out NLL in the checkpoint matrix.
- Order-2 safety mix as primary safety candidate: demoted because
  shaped order 3 has better entropy and quality in the checkpoint matrix.

## Remaining Uncertainty

- Payload coverage is still bounded. The matrix includes empty, small text,
  structured text, and 256-byte binary payloads, but not large-file archival
  workloads.
- Corpus coverage uses deterministic synthetic domains. Real text corpora may
  change the ranking.
- Transformer work remains immature. The pinned fixture is not competitive, but
  stronger deterministic training may change the future research direction.
- Runtime speed was not used as a promotion metric beyond bounded completion.

## Merge Recommendation

Merge V2 as a stronger research baseline, not as planning-only.

This branch now contains reproducible checkpoint tooling, deterministic
payload and matrix specs, measured candidate rankings, and candidate reports.
It should not be presented as a new codec format or production release. The
right merge framing is:

- V1 remains the correctness contract.
- V2 adds promotion-grade research scaffolding and measured carrier baselines.
- The current V2 quality candidate is unshaped order 3.
- The current V2 safety and balanced candidate is shaped order 3.
