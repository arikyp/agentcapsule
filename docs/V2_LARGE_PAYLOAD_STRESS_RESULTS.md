# V2 Large Payload Stress Results

Date: 2026-05-08

Matrix:

- `experiments/matrices/v2_large_payload_realish.json`
- Output: `experiments/runs/v2_large_payload_realish_matrix`
- Run mode: `--resume --timeout-seconds 30`

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

## Result Summary

The 1KB and 10KB cells passed hard gates. The 100KB cells exposed the current
runtime boundary.

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
- 100KB payloads are not practical as routine pure-Python matrix cells with the
  current runner/model path.

## Runtime Finding

The first uncapped run reached `order3_quality / v2_reports / text_100kb` and
eventually completed that cell with:

- Encode: `1193.488s`
- Decode: `220.153s`
- Roundtrip: pass
- Entropy: `5.927`
- NLL: `4.633`

That result is important: the 100KB path can work, but it is far too slow for a
normal checkpoint matrix. Runtime is now a real research constraint, not just a
secondary metric.

## Hard-Gate Interpretation

The 30 second capped run records 100KB timeouts as hard-gate failures. This is
intentional. The failure is not evidence of decode incorrectness; it is
evidence that the current pure-Python carrier path is too slow at this payload
size under routine experiment budgets.

## Recommendation

Do not train a Transformer yet.

The next substantive step should be runtime-focused:

1. Add a smaller large-payload ladder such as 16KB, 32KB, and 64KB to find the
   practical knee.
2. Profile encode for n-gram carriers on one slow cell.
3. Optimize or cache the hot path only if profiling points to a clear local
   target.
4. Rerun the real-ish corpus matrix after runtime instrumentation improves.

The current candidate decision remains:

- Quality: `order3_quality`
- Balanced/safety: `order3_balanced_shape`
- Fallback: `order2_safety_mix`
