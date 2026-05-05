# Benchmarking

LMCodec experiment scripts print their existing console reports by default.
For reproducible experiment tracking, the Python scripts can also write
structured JSON with `--json-out`.

The JSON includes:

- UTC timestamp and git commit when available.
- Payload path, byte count, SHA256, and base64 baseline length.
- Model type, fingerprint, and model path when applicable.
- Codec and shaping settings.
- Carrier character count, full armour character count, and bits per carrier character.
- Encode and decode wall-clock seconds.
- Roundtrip success or failure and error message.
- Held-out NLL, entropy, and top-token probability when quality text is supplied.
- Encoded-carrier diversity and character-frequency divergence metrics.
- Convergence failure count when an experiment fails during encode convergence.

Runtime fields such as timestamp and encode/decode seconds are expected to vary
between runs. Other fields should remain deterministic for the same payload,
model, settings, and git revision.

## JSON Contract

Benchmark JSON currently uses `schema_version: 1`. The documented schema is
committed at [schemas/benchmark_result_v1.json](../schemas/benchmark_result_v1.json).

The repository does not depend on a JSON Schema validator at runtime. The schema
is a stable contract for downstream tooling and future validation tests.

## Compare Models

Compare the fixed carrier with an order-1 n-gram carrier and write JSON:

```bash
scripts/compare_models.py \
  --payload payload.bin \
  --corpus examples/carrier_train_v2.txt \
  --quality-text examples/carrier_heldout_v2.txt \
  --json-out benchmark-compare.json
```

Include a pinned Transformer model:

```bash
scripts/compare_models.py \
  --payload payload.bin \
  --corpus examples/carrier_train_v2.txt \
  --quality-text examples/carrier_heldout_v2.txt \
  --transformer-model tests/fixtures/transformer_model_v1.json \
  --shape-uniform-mix 0.80 \
  --temperature 1.25 \
  --max-steps 100000 \
  --json-out benchmark-transformer.json
```

## Sweep Shaping

Run a small shaping sweep for an exported Transformer model:

```bash
scripts/sweep_shaping.py \
  --model tests/fixtures/transformer_model_v1.json \
  --payload payload.bin \
  --quality-text examples/carrier_heldout_v2.txt \
  --uniform-mixes 0.80,0.90 \
  --temperatures 1.25,1.75 \
  --min-probs 0.0 \
  --json-out benchmark-sweep.json
```

The sweep script records failed settings in JSON when it can continue. Failed
rows have `roundtrip_success: false`, metric fields set to `null`, and an
`error_message` describing the failure.

## Shell Demos

The shell demo scripts still use the CLI and keep their console behaviour:

```bash
sh scripts/demo_roundtrip.sh
sh scripts/demo_compare.sh
sh scripts/demo_transformer.sh
```

Use `compare_models.py` or `sweep_shaping.py` with `--json-out` when a
machine-readable experiment record is needed.
