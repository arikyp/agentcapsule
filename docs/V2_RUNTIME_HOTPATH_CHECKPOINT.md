# V2 Runtime Hot Path Checkpoint

Date: 2026-05-08

Branch: `codex/v2-profile-encode-hotpath`

## Scope

This checkpoint optimizes measured runtime hot paths without changing codec
semantics, golden fixtures, frame layout, armour behavior, or runtime
dependencies.

The profiling target came from the V2 size ladder:

```bash
scripts/profile_experiment.py \
  experiments/runs/v2_size_ladder_matrix/configs/v2-size-ladder-order3_quality-project_docs-binary_32kb.json \
  --limit 50 \
  --profile-out experiments/runs/v2_size_ladder_matrix/order3_quality_binary_32kb.prof
```

Initial profile result:

- Total profiled runtime: `190.726s`
- Encode: `152.476s`
- Decode: `36.479s`
- Main encode cost: repeated `RangeEncoder.preview_finish()` cloning and
  tuple materialization in prefix checks.

## Changes

- Added range encoder helpers for emitted bit count, prefix slicing, incremental
  emitted-prefix checks, and finish-preview prefix checks.
- Updated encode to compare only newly emitted bits after each symbol instead
  of rematerializing the whole emitted bit tuple.
- Updated decode to parse the frame header once, then wait until the known
  frame bit length is available before materializing and parsing frame bits.
- Added per-call CDF caching in encode/decode so repeated model distributions
  reuse the same shaped and quantized CDF.
- Added quality-metric shaping caches so matrix reporting does not repeatedly
  reshape identical heldout distributions.
- Kept range-coder CDF validation as the public default, but let the codec use
  an unchecked path for CDFs produced by LMCodec's own quantizer.

These changes preserve the range-coder stream and only avoid repeated local
work around prefix, frame, and deterministic distribution preparation.

## Measured Results

Representative `order3_quality / project_docs / binary_32kb` result:

| State | Encode seconds | Decode seconds | Roundtrip |
| --- | ---: | ---: | --- |
| Size ladder baseline | 137.539 | 23.129 | pass |
| After encode prefix optimization | 6.630 | 22.877 | pass |
| After encode and decode optimization | 6.504 | 5.960 | pass |
| After distribution caching | 1.073 | 0.528 | pass |

Former 64KB timeout cell:

| Payload | Encode seconds | Decode seconds | Roundtrip |
| --- | ---: | ---: | --- |
| `binary_64kb` after prefix/frame fixes | 13.564 | 11.773 | pass |
| `binary_64kb` after distribution caching | 2.145 | 1.025 | pass |

Large-payload stress spot check:

| Matrix cell | Encode seconds | Decode seconds | Roundtrip |
| --- | ---: | ---: | --- |
| `order3_quality / project_docs / binary_100kb` after prefix/frame fixes | 20.997 | 18.343 | pass |
| `order3_quality / project_docs / binary_100kb` after distribution caching | 3.301 | 1.576 | pass |

That 100KB cell was previously outside routine budget; one earlier uncapped
100KB text cell took `1193.488s` encode and `220.153s` decode.

## Post-Optimization Profile

Profile after prefix/frame fixes:

- Total profiled runtime: `40.098s`
- Encode: `19.667s`
- Decode: `18.278s`
- Top remaining costs:
  - `shape_probabilities`: `19.533s`
  - `quantize`: `14.669s`
  - probability normalization and entropy calculations

The prefix and repeated frame-probing costs are no longer the controlling
runtime issue.

Final profile after distribution caching:

- Total profiled runtime: `4.357s`
- Encode: `2.373s`
- Decode: `1.193s`
- Top remaining costs:
  - range-coder arithmetic in `push_symbol` and `pop_symbol`
  - CDF cache lookups
  - model `step_probs` / `advance`
  - quality metrics, now `0.559s`

The former probability shaping and quantization hot path is now bounded to
cache misses.

## Verification

Commands run:

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.test_range_coder tests.test_range_coder_stress tests.test_codec tests.test_golden
PYTHONPATH=src .venv/bin/python -m unittest tests.test_range_coder tests.test_range_coder_stress tests.test_codec tests.test_golden tests.test_experiments
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
sh scripts/verify_v1.sh
```

Results:

- Focused tests: `23` passed
- Full tests: `75` passed
- V1 verification: passed

## Recommendation

This branch should merge as a runtime strengthening of the V2 research
baseline. The practical payload ceiling has moved materially: 64KB no longer
times out for the profiled order-3 quality cell, and a 100KB real-ish binary
stress cell completes in under 5 seconds of measured encode/decode time.

Follow-up matrix broadening completed in
`docs/V2_LARGE_PAYLOAD_STRESS_RESULTS.md`: all 36 large-payload real-ish cells
passed hard gates under a 60-second per-cell cap. The next substantive step is
broader corpus realism and larger payload sizes before changing model family.
If another runtime optimization is needed, the next measured target is
range-coder arithmetic cost rather than probability or frame probing.
