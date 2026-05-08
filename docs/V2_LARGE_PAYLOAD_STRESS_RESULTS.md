# V2 Large Payload Stress Results

Date: 2026-05-08

Update: the runtime hot-path checkpoint in
`docs/V2_RUNTIME_HOTPATH_CHECKPOINT.md` superseded the original runtime
boundary reported here. A fresh full rerun after those runtime fixes is now the
current large-payload result.

Matrix:

- `experiments/matrices/v2_large_payload_realish.json`
- Output: `experiments/runs/v2_large_payload_realish_matrix`
- Run mode: `--resume --timeout-seconds 30`

Rerun mode after runtime fixes:

```bash
scripts/run_matrix.py experiments/matrices/v2_large_payload_realish.json --timeout-seconds 60
```

## Runtime-Fixed Rerun

The full 36-cell matrix passed hard gates after the runtime hot-path fixes.

| Candidate | Hard-gate failures | Mean NLL | Mean entropy | Mean encode seconds | Mean decode seconds |
| --- | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 0 | 4.711 | 5.928 | 1.265 | 0.608 |
| `order2_safety_mix` | 0 | 4.914 | 5.941 | 1.217 | 0.626 |
| `order3_balanced_shape` | 0 | 4.940 | 5.960 | 1.300 | 0.626 |

100KB-only summary:

| Candidate | 100KB cells | Mean encode seconds | Mean decode seconds | Max encode seconds | Max decode seconds | Mean NLL | Mean entropy |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `order3_quality` | 4 | 3.335 | 1.572 | 3.512 | 1.602 | 4.711 | 5.928 |
| `order2_safety_mix` | 4 | 3.146 | 1.589 | 3.268 | 1.708 | 4.914 | 5.941 |
| `order3_balanced_shape` | 4 | 3.436 | 1.628 | 3.665 | 1.764 | 4.940 | 5.960 |

Interpretation after the rerun:

- 100KB deterministic binary and text payloads are now practical routine matrix
  cells for these n-gram candidates.
- `order3_quality` remains the quality winner by NLL.
- `order3_balanced_shape` remains the entropy/safety winner.
- `order2_safety_mix` remains a viable fallback, but it no longer has a
  material runtime advantage over order 3.
- The balanced candidate decision does not change: use `order3_quality` when
  quality is the priority and `order3_balanced_shape` when the entropy margin is
  the priority.

## Scope

The matrix tested three n-gram candidates against larger deterministic payloads
and local real-ish corpora. It intentionally did not train or evaluate a
Transformer candidate.

Candidates:

- `order3_quality`
- `order3_balanced_shape`
- `order2_safety_mix`

Corpora:

- `project_docs`
- `v2_reports`

Payloads:

- `binary_1kb`
- `binary_10kb`
- `binary_100kb`
- `text_1kb`
- `text_10kb`
- `text_100kb`

## Original Capped Result Summary

Before the runtime hot-path fixes, the 1KB and 10KB cells passed hard gates.
The 100KB cells exposed the then-current runtime boundary.

With a 30 second per-cell timeout:

| Candidate | Hard-gate failures | Mean NLL | Mean entropy | Mean encode seconds |
| --- | ---: | ---: | ---: | ---: |
| `order3_quality` | 3 | 4.722 | 5.929 | 140.728 |
| `order2_safety_mix` | 4 | 4.929 | 5.941 | 10.434 |
| `order3_balanced_shape` | 4 | 4.958 | 5.961 | 9.656 |

Interpretation:

- `order3_quality` remains the best quality candidate on NLL.
- `order3_balanced_shape` remains the strongest entropy candidate.
- `order2_safety_mix` did not recover enough quality to justify replacing
  shaped order 3.
- At this point in the branch history, 100KB payloads were not practical as
  routine pure-Python matrix cells.

## Runtime Finding

The first uncapped run reached `order3_quality / v2_reports / text_100kb` and
eventually completed that cell with:

- Encode: `1193.488s`
- Decode: `220.153s`
- Roundtrip: pass
- Entropy: `5.927`
- NLL: `4.633`

That result was important: the 100KB path could work, but it was far too slow
for a normal checkpoint matrix before the runtime hot-path fixes.

## Hard-Gate Interpretation

The 30 second capped run records 100KB timeouts as hard-gate failures. This is
intentional. The failure is not evidence of decode incorrectness; it is
evidence that the current pure-Python carrier path is too slow at this payload
size under routine experiment budgets.

## Recommendation

Do not train a Transformer yet.

The runtime-focused step has now paid off, and 100KB n-gram matrix cells are
back inside routine budget. The next substantive step should move up one level:
use the new runtime headroom to test broader corpus realism and larger payload
sizes before changing model family.

The current candidate decision remains:

- Quality: `order3_quality`
- Balanced/safety: `order3_balanced_shape`
- Fallback: `order2_safety_mix`
