# V2 Real Corpus Payload Ladder Results

Date: 2026-05-08

Matrix:

- `experiments/matrices/v2_real_corpus_payload_ladder.json`
- Output: `experiments/runs/v2_real_corpus_payload_ladder_matrix`
- Run mode: `--timeout-seconds 120`

## Scope

This matrix used the runtime headroom from
`docs/V2_RUNTIME_HOTPATH_CHECKPOINT.md` to test larger payloads and broader
local corpora before moving to Transformer training.

Payloads:

- `binary_256kb`
- `binary_512kb`
- `text_256kb`
- `text_512kb`

Corpora:

- `repo_code_docs`: README, changelog, pyproject, algorithm/benchmarking docs,
  V2 result docs, codec/range/probability/quantizer/LM source, and experiment
  runner scripts.
- `tests_and_protocol`: testing/release/protocol docs plus codec, golden,
  property, range-coder, matrix, probability, and quantizer tests.

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `order2_safety_mix`

## Results

The full 24-cell matrix passed hard gates.

| Candidate | Hard-gate failures | Mean NLL | Mean entropy | Mean encode seconds | Mean decode seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 0 | 4.487 | 5.877 | 12.593 | 6.201 |
| `order3_balanced_shape` | 0 | 4.747 | 5.932 | 12.481 | 6.050 |
| `order2_safety_mix` | 0 | 4.815 | 5.919 | 11.731 | 5.786 |

Payload-size summary:

| Payload | Mean encode seconds | Mean decode seconds | Max encode seconds | Max decode seconds |
| --- | ---: | ---: | ---: | ---: |
| `binary_256kb` | 8.331 | 4.050 | 8.570 | 4.425 |
| `binary_512kb` | 16.297 | 8.092 | 16.814 | 9.615 |
| `text_256kb` | 8.349 | 4.047 | 9.043 | 4.489 |
| `text_512kb` | 16.095 | 7.859 | 16.938 | 8.062 |

512KB-only candidate summary:

| Candidate | 512KB cells | Mean encode seconds | Mean decode seconds | Max encode seconds | Max decode seconds | Mean NLL | Mean entropy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 4 | 16.651 | 8.231 | 16.938 | 9.615 | 4.487 | 5.877 |
| `order3_balanced_shape` | 4 | 16.397 | 7.987 | 16.673 | 8.281 | 4.747 | 5.932 |
| `order2_safety_mix` | 4 | 15.541 | 7.710 | 15.838 | 7.858 | 4.815 | 5.919 |

## Readout

Hard gates are no longer the limiting factor up to 512KB for these n-gram
candidates on broader local corpora.

The candidate decision still holds:

- Quality candidate: `order3_quality`
- Entropy/safety candidate: `order3_balanced_shape`
- Fallback candidate: `order2_safety_mix`

Runtime no longer justifies preferring order 2. It is slightly faster, but not
enough to offset the weaker NLL and lower entropy than the shaped order-3
candidate.

The 512KB results are close to linear with payload size and remain well inside
the 120-second per-cell cap. The next ceiling-finding payload should be 1MB,
but that requires raising `max_steps` above this matrix's 5,000,000 budget.

## Recommendation

Do not train a Transformer yet.

The next substantive branch should stress:

- 1MB deterministic binary/text payloads,
- a larger or external corpus source,
- the current quality and balanced order-3 candidates first,
- order-2 only as a fallback comparator.

If 1MB passes with the same candidate ordering, then V2 has enough n-gram
runtime and safety evidence to justify either a merge as a stronger baseline or
a carefully scoped Transformer-training branch.
