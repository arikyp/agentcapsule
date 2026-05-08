# Experiments

This directory holds bounded LMCodec experiment configs and generated run
outputs.

Example configs live in `experiments/configs/`:

- `example_fixed.json`
- `example_ngram.json`
- `example_transformer.json`
- `v2_*.json`

Run an experiment from the repository root:

```bash
scripts/run_experiment.py experiments/configs/example_fixed.json
```

Each run writes an output directory containing:

- `result.json`
- `carrier.txt`
- `decoded_payload.bin`
- `model.json` when the model is trained/exported by the run

Generated run directories are reproducible artifacts, but they can grow over
time. Keep only the runs that are useful for comparison.

Compare completed runs:

```bash
scripts/compare_results.py experiments/runs/*/result.json
```

Run the V2 checkpoint matrix:

```bash
scripts/run_matrix.py experiments/matrices/v2_checkpoint.json
```

Run the larger real-ish corpus stress matrix:

```bash
scripts/run_matrix.py experiments/matrices/v2_large_payload_realish.json
```
