# V2 Experiment Protocol

V2 experiments are bounded carrier-model runs. They should make candidate
carrier text less artificial while preserving deterministic transport.

## Required Flow

1. Create or choose a JSON config under `experiments/configs/`.
2. Run the config with `scripts/run_experiment.py`.
3. Inspect the generated `result.json`.
4. Compare against the current V2 baseline.
5. Promote only if all promotion checks pass and at least one quality metric
   improves.

Example:

```bash
scripts/run_experiment.py experiments/configs/v2_ngram_mixed_5k_order1.json
```

## Config Rules

Each V2 config should include:

- `experiment_name`
- `payload_path`
- `model`
- `shape_settings`
- `max_steps`
- `run_golden_tests`
- `wrap`
- `quality_text_path`
- `promotion_gate`
- `output_dir`

Use separate output directories for separate candidates. Do not reuse an
existing output directory unless intentionally replacing that exact run.

## Promotion Gate

Promotion requires:

- `roundtrip_success == true`
- decoded payload SHA256 equals input payload SHA256
- `model_fingerprint_stable == true`
- entropy is at or above the configured minimum
- `convergence_failure_count == 0`
- V1 golden tests are unaffected when checked
- no unexpected error message

Metric improvement alone is not enough. A candidate with better held-out NLL
but lower entropy than the gate should fail.

## Comparison Fields

Use these fields first:

- `roundtrip_success`
- `promotion.passed`
- `bits_per_carrier_char`
- `heldout_nll_bits`
- `avg_entropy_bits`
- `avg_top_probability`
- `carrier_diversity.unique_character_count`
- `carrier_diversity.longest_repeated_run`
- `carrier_diversity.char_frequency_l1_divergence`
- `carrier_diversity.char_frequency_kl_bits`

Runtime fields such as timestamp and encode/decode seconds are useful for
debugging but should not be treated as deterministic improvement signals.

## Corpus Track

For corpus experiments:

```bash
scripts/build_carrier_corpus.py \
  --out examples/carrier_corpus_v2.txt \
  --lines 5000 \
  --seed 42 \
  --domain mixed \
  --report-json /tmp/carrier-corpus-report.json

scripts/split_corpus.py \
  --input examples/carrier_corpus_v2.txt \
  --train-out examples/carrier_train_v2.txt \
  --heldout-out examples/carrier_heldout_v2.txt \
  --heldout-ratio 0.20 \
  --filter-vocab \
  --report-json /tmp/carrier-split-report.json
```

Keep domain, line count, seed, and split ratio explicit in any report.

## Shaping Track

For Transformer shaping sweeps:

```bash
scripts/sweep_shaping.py \
  --model tests/fixtures/transformer_model_v1.json \
  --payload pyproject.toml \
  --quality-text examples/carrier_heldout_v2.txt \
  --uniform-mixes 0.4,0.6,0.75,0.85 \
  --temperatures 1.0,1.15,1.25,1.4 \
  --min-entropy-bits 5.8 \
  --json-out experiments/runs/v2_transformer_fixture_sweep/result.json
```

Prefer bounded sweeps with small grids. Large search spaces should be split
into repeatable batches.

## Guardrails

- Do not mutate V1 golden fixtures for V2 work.
- Do not change frame or armour semantics without explicit versioning.
- Do not promote based on greedy preview text.
- Do not accept non-deterministic training artifacts as fixtures.
- Do not let generated experiment artifacts drift into source control unless
  they are intentionally chosen as reproducible baselines.

## Checkpoint Matrices

Use `scripts/run_matrix.py` when a candidate needs promotion-grade research
coverage across payloads and corpus domains:

```bash
scripts/run_matrix.py experiments/matrices/v2_checkpoint.json
```

The matrix runner writes deterministic payloads, deterministic corpus splits,
generated configs, per-run artifacts, and `matrix_result.json` under its output
directory. Generated matrix artifacts stay under `experiments/runs/` and are
ignored by git.

Matrix rankings use hard gates before quality metrics:

- no error
- roundtrip success
- decoded SHA256 matches payload SHA256
- model fingerprint stability
- entropy above configured minimum
- no convergence failure

V1 golden fixture safety is verified separately with `sh scripts/verify_v1.sh`
and `sh scripts/release_check.sh` for checkpoint work, rather than repeated
inside every matrix cell.
