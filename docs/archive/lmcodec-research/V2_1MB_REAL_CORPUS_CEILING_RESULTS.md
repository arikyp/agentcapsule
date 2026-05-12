# V2 1MB Real Corpus Ceiling Results

Date: 2026-05-08

Branch: `codex/v2-1mb-real-corpus-ceiling`

Matrix:

- `experiments/matrices/v2_1mb_real_corpus_ceiling.json`
- Output: `experiments/runs/v2_1mb_real_corpus_ceiling_matrix`
- Run mode: `--timeout-seconds 180`

## Scope

This matrix follows the 512KB ladder in
`docs/V2_REAL_CORPUS_PAYLOAD_LADDER_RESULTS.md`. It tests whether the current
runtime-strengthened n-gram candidates remain practical at 1MB before starting
any Transformer training branch.

Payloads:

- `binary_1mb`
- `text_1mb`

Corpora:

- `all_repo_text`: broad local docs, source, and runner scripts.
- `all_tests_protocol`: protocol docs plus the full local test suite.

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `order2_safety_mix`

## Results

The full 12-cell matrix passed hard gates.

| Candidate | Hard-gate failures | Mean NLL | Mean entropy | Mean encode seconds | Mean decode seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 0 | 4.235 | 5.828 | 31.937 | 15.513 |
| `order3_balanced_shape` | 0 | 4.531 | 5.906 | 32.344 | 15.517 |
| `order2_safety_mix` | 0 | 4.708 | 5.903 | 31.146 | 15.241 |

Payload summary:

| Payload | Mean encode seconds | Mean decode seconds | Max encode seconds | Max decode seconds |
| --- | ---: | ---: | ---: | ---: |
| `binary_1mb` | 31.891 | 15.374 | 32.610 | 15.799 |
| `text_1mb` | 31.727 | 15.474 | 32.983 | 16.001 |

Candidate summary:

| Candidate | 1MB cells | Mean encode seconds | Mean decode seconds | Max encode seconds | Max decode seconds | Mean NLL | Mean entropy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 4 | 31.937 | 15.513 | 32.342 | 15.686 | 4.235 | 5.828 |
| `order3_balanced_shape` | 4 | 32.344 | 15.517 | 32.983 | 16.001 | 4.531 | 5.906 |
| `order2_safety_mix` | 4 | 31.146 | 15.241 | 31.276 | 15.549 | 4.708 | 5.903 |

## Readout

The 1MB ceiling pass did not expose a hard-gate failure. Runtime remains roughly
linear from the 512KB ladder, with the slowest cell still under 33 seconds of
measured encode time and 17 seconds of measured decode time.

The candidate decision still holds:

- Quality candidate: `order3_quality`
- Entropy/safety candidate: `order3_balanced_shape`
- Fallback candidate: `order2_safety_mix`

Order 2 is slightly faster, but it is not enough to justify replacing the
order-3 candidates. `order3_balanced_shape` has nearly the same entropy as
order 2 with substantially better NLL.

## Recommendation

This is enough n-gram evidence to merge V2 as a stronger research baseline once
the stacked runtime branch is merged or included.

The next research branch can now be Transformer-focused, but it should be scoped
as a comparison branch against these n-gram results rather than a replacement
branch. The Transformer branch should use this 1MB matrix as a regression and
budget reference, not as a first training target.
