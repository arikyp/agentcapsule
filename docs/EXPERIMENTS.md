# Experiments

`scripts/run_experiment.py` is a bounded V2 experiment scaffold. It runs one
carrier configuration from a JSON config and writes reproducible artifacts. It
does not implement an autonomous research agent.

## Run An Experiment

From the repository root:

```bash
scripts/run_experiment.py experiments/configs/example_fixed.json
scripts/run_experiment.py experiments/configs/example_ngram.json
scripts/run_experiment.py experiments/configs/example_transformer.json
```

Each config writes to its `output_dir`:

- `result.json`
- `carrier.txt`
- `decoded_payload.bin`
- `model.json` when the run trains or exports a model

The console summary reports the experiment name, roundtrip status, promotion
status, carrier length, bits per carrier character, entropy when available, and
the result JSON path.

## Config Shape

Minimal fixed-carrier config:

```json
{
  "experiment_name": "example-fixed",
  "payload_path": "pyproject.toml",
  "model": {
    "type": "fixed"
  },
  "shape_settings": {
    "uniform_mix": 0.0,
    "temperature": 1.0,
    "min_probability": 0.0,
    "min_entropy_bits": 0.0
  },
  "max_steps": 100000,
  "quality_text_path": "examples/carrier_heldout_v1.txt",
  "promotion_gate": {
    "min_entropy_bits": 5.9
  },
  "output_dir": "experiments/runs/example_fixed"
}
```

Model types:

- `fixed`: uses the built-in fixed 64-symbol carrier.
- `ngram`: either load `"path"` or train from `"training": {"corpus_path": ...}`.
- `transformer`: either load `"path"` or train from `"training": {"corpus_path": ...}`.

Relative paths are resolved from the current working directory when possible,
then relative to the config file, then relative to the repository root.

## Result Metrics

`result.json` includes:

- Timestamp UTC and git commit when available.
- Payload path, byte count, SHA256, and base64 baseline length.
- Decoded payload SHA256.
- Model type, fingerprint, source path, and fingerprint stability check.
- Shape settings.
- Carrier chars, full armour chars, and bits per carrier char.
- Encode and decode seconds.
- Roundtrip success.
- Held-out NLL, average entropy, and average top-token probability when
  `quality_text_path` is provided.
- Carrier diversity:
  - unique character count
  - character frequency distribution
  - longest repeated run
  - character frequency divergence against held-out text when available
  - preview sample
- Promotion gate checks.
- Artifact paths.

Runtime fields such as timestamp and encode/decode seconds vary between runs.
For the same config, payload, model, and git commit, deterministic fields such
as payload SHA256, model fingerprint, carrier text, decoded payload SHA256, and
carrier diversity should remain stable.

## Promotion Gate

A run is promoted only when all checks pass:

- Roundtrip succeeds.
- Decoded payload SHA256 equals input payload SHA256.
- Model fingerprint remains stable during the run.
- Average entropy is at or above `promotion_gate.min_entropy_bits` when that
  gate is configured.
- Encode does not hit a convergence failure.
- Golden tests are not affected by the run.

The runner does not execute golden tests itself. The `golden_tests_unaffected`
check records the contract: experiment runs must not mutate fixtures or codec
semantics. Use the normal test suite and `scripts/verify_v1.sh` after code
changes.

## Comparing Runs

Run configs into separate output directories, then compare `result.json` files:

```bash
scripts/run_experiment.py experiments/configs/example_fixed.json
scripts/run_experiment.py experiments/configs/example_ngram.json
scripts/run_experiment.py experiments/configs/example_transformer.json
```

Useful fields for comparison:

- `roundtrip_success`
- `promotion.passed`
- `bits_per_carrier_char`
- `heldout_nll_bits`
- `avg_entropy_bits`
- `avg_top_probability`
- `carrier_diversity.unique_character_count`
- `carrier_diversity.longest_repeated_run`

Prefer changes that improve held-out quality or carrier diversity without
breaking deterministic roundtrip, entropy, or golden fixture checks.
