# V2 Size Ladder

## Goal

Find the practical runtime knee between the known-good 10KB payloads and the
impractical 100KB payloads.

The large-payload stress matrix showed:

- 1KB and 10KB payloads pass hard gates.
- 100KB payloads are not practical under routine matrix budgets.
- One 100KB text cell completed, but took about `1193s` encode and `220s`
  decode.

The size ladder narrows the gap.

## Matrix

Spec:

- `experiments/matrices/v2_size_ladder.json`

Payloads:

- `binary_16kb`
- `binary_32kb`
- `binary_64kb`
- `text_16kb`
- `text_32kb`
- `text_64kb`

Corpus:

- `project_docs`

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `order2_safety_mix`

## Suggested Run

Use resume and a per-cell cap:

```bash
scripts/run_matrix.py experiments/matrices/v2_size_ladder.json \
  --resume \
  --timeout-seconds 180
```

The run writes:

```text
experiments/runs/v2_size_ladder_matrix/matrix_result.json
experiments/runs/v2_size_ladder_matrix/matrix_progress.jsonl
```

## Decision Rule

The ladder should identify the largest payload size that passes hard gates
within the timeout budget for each candidate.

Interpretation:

- If 16KB fails or times out, runtime work is urgent before further modeling.
- If 16KB and 32KB pass but 64KB fails, set the temporary V2 matrix budget
  below 64KB.
- If all sizes pass, repeat with a higher ladder before revisiting
  Transformer training.

Runtime is still secondary to hard gates, but it is now the main practical
constraint for larger payloads.

## Results

The partial ladder results are recorded in:

- `docs/V2_SIZE_LADDER_RESULTS.md`
