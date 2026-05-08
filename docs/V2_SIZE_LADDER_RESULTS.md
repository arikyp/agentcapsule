# V2 Size Ladder Results

Date: 2026-05-08

Matrix:

- `experiments/matrices/v2_size_ladder.json`
- Output: `experiments/runs/v2_size_ladder_matrix`
- Run mode: `--resume --timeout-seconds 180`

The run was intentionally stopped after the key runtime boundary was clear.
Continuing through every remaining candidate/payload combination would not
change the immediate next step.

## Partial Results

| Candidate | Payload | Hard gate | Encode seconds | Decode seconds | NLL | Entropy |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| `order3_quality` | `binary_16kb` | pass | 47.672 | 7.973 | 4.780 | 5.926 |
| `order3_quality` | `binary_32kb` | pass | 137.539 | 23.129 | 4.780 | 5.926 |
| `order3_quality` | `binary_64kb` | timeout |  |  |  |  |
| `order3_quality` | `text_16kb` | pass | 48.850 | 7.400 | 4.780 | 5.926 |
| `order3_quality` | `text_32kb` | pass | 136.289 | 23.314 | 4.780 | 5.926 |
| `order3_quality` | `text_64kb` | timeout |  |  |  |  |
| `order3_balanced_shape` | `binary_16kb` | pass | 58.330 | 10.183 | 4.996 | 5.959 |
| `order3_balanced_shape` | `binary_32kb` | timeout |  |  |  |  |
| `order3_balanced_shape` | `binary_64kb` | timeout |  |  |  |  |
| `order3_balanced_shape` | `text_16kb` | pass | 48.286 | 8.951 | 4.996 | 5.959 |

## Readout

The practical knee is between 32KB and 64KB for unshaped order 3 under a
180-second per-cell cap.

Key points:

- `order3_quality` reaches 32KB for both deterministic binary and text
  payloads.
- `order3_quality` times out at 64KB.
- `order3_balanced_shape` improves entropy, but it does not improve runtime.
- `order3_balanced_shape` already times out on `binary_32kb`.

This is enough to set a temporary V2 routine matrix budget:

- Routine stress ceiling: `32KB`
- Runtime-profiling target: `order3_quality / project_docs / binary_32kb`
- Avoid routine 64KB and 100KB matrix cells until the encode hot path is
  profiled and improved.

## Next Step

Profile one representative passing-but-slow cell:

```bash
scripts/run_experiment.py \
  experiments/runs/v2_size_ladder_matrix/configs/v2-size-ladder-order3_quality-project_docs-binary_32kb.json
```

Use profiling to identify the encode hot path before changing any model or
codec semantics.

Profiling helper:

```bash
scripts/profile_experiment.py \
  experiments/runs/v2_size_ladder_matrix/configs/v2-size-ladder-order3_quality-project_docs-binary_32kb.json \
  --limit 40 \
  --profile-out experiments/runs/v2_size_ladder_matrix/order3_quality_binary_32kb.prof
```
