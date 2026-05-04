# LMCodec

LMCodec is a planned lossless text transport codec. It converts arbitrary bytes
into plausible-looking text and reconstructs the original bytes bit-perfectly.

The codec uses a language model as the probability source and a deterministic
range coder as the bit-to-symbol mapping layer. The practical goal is a
"text-only USB stick": if a system can preserve copy/pasted text, it can carry
binary data through LMCodec.

## Project Status

V1 research prototype implemented.

Current implementation includes:

- Deterministic quantizer.
- Deterministic probability shaping before quantization.
- Integer arithmetic coder.
- Binary frame with magic, payload length, and CRC32.
- Copy/paste armour.
- Fixed 64-symbol carrier model.
- Deterministic n-gram model backend with JSON serialization.
- Experimental deterministic Transformer-style carrier backend.
- Pinned golden fixtures for fixed, n-gram, and Transformer carriers.
- File encode/decode CLI.
- Unit and end-to-end tests.

The fixed carrier remains the stable default. The Transformer carrier is
experimental but pinned and reproducible as a V1 fixture.

The implementation plan is in [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md).
The V1 release checkpoint is summarized in [docs/V1_RELEASE.md](docs/V1_RELEASE.md).
Start with [docs/QUICKSTART.md](docs/QUICKSTART.md) for installed CLI usage,
and [docs/LIMITATIONS.md](docs/LIMITATIONS.md) for V1 boundaries.

## V1 Priorities

- Lossless byte-for-byte roundtrip.
- Deterministic output for identical input, model, and settings.
- Simple implementation with minimal dependencies.
- Clear armour format for copy/paste transport.
- Golden regression fixture to catch drift.

## Non-Goals

- Maximum compression ratio.
- GPU-first model execution.
- Semantically meaningful generated text.
- Complex model architecture before the arithmetic layer is proven.

## CLI

```bash
PYTHONPATH=src python3 -m lmcodec.cli encode --in payload.bin --out message.txt --wrap 80
PYTHONPATH=src python3 -m lmcodec.cli decode --in message.txt --out payload.bin
```

Train and use a deterministic n-gram model:

```bash
PYTHONPATH=src python3 -m lmcodec.cli train --data corpus.txt --out model.json --order 1 --uniform-mix 0.75
PYTHONPATH=src python3 -m lmcodec.cli encode --model model.json --in payload.bin --out message.txt --wrap 80
PYTHONPATH=src python3 -m lmcodec.cli decode --model model.json --in message.txt --out payload.bin
```

Train and use the experimental Transformer-style carrier:

```bash
PYTHONPATH=src python3 -m lmcodec.cli train \
  --model-type transformer \
  --data examples/carrier_train_v2.txt \
  --out transformer.json \
  --block-size 8 \
  --d-model 8 \
  --ff-dim 12
PYTHONPATH=src python3 -m lmcodec.cli encode \
  --model transformer.json \
  --in payload.bin \
  --out message.txt \
  --wrap 80 \
  --shape-uniform-mix 0.85 \
  --temperature 1.5
PYTHONPATH=src python3 -m lmcodec.cli decode --model transformer.json --in message.txt --out payload.bin
```

The current Transformer backend is intentionally small: a deterministic causal
attention feature extractor with a trained output head. It proves the model
interface, serialization, fingerprinting, and codec roundtrip path before full
end-to-end Transformer backprop is added.

Use `--uniform-mix` to control how aggressively the trained distribution is
flattened toward uniform. Higher values improve transport capacity and reduce
the chance of hitting the encode convergence limit. `--order 1 --uniform-mix
0.75` is the current recommended non-uniform demo setting.

If needed, encode accepts `--max-steps` to raise the deterministic convergence
limit for heavily skewed models.

## Tests

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

Full V1 verification:

```bash
sh scripts/verify_v1.sh
```

Installed CLI release check:

```bash
sh scripts/release_check.sh
```

## Demo

```bash
sh scripts/demo_roundtrip.sh
```

Compare the fixed carrier against the trained order-1 n-gram carrier:

```bash
sh scripts/demo_compare.sh
```

Run the pinned Transformer carrier demo:

```bash
sh scripts/demo_transformer.sh
```

Create deterministic train/held-out corpus splits:

```bash
scripts/build_carrier_corpus.py \
  --out examples/carrier_corpus_v2.txt \
  --lines 5000 \
  --seed 42
scripts/split_corpus.py \
  --input examples/carrier_corpus_v2.txt \
  --train-out examples/carrier_train_v2.txt \
  --heldout-out examples/carrier_heldout_v2.txt \
  --heldout-ratio 0.20 \
  --filter-vocab
```

Run the reusable experiment harness with optional probability shaping:

```bash
scripts/compare_models.py \
  --payload payload.bin \
  --corpus examples/carrier_train_v2.txt \
  --quality-text examples/carrier_heldout_v2.txt \
  --include-transformer \
  --shape-uniform-mix 0.85 \
  --temperature 1.5
```

Compare a previously exported Transformer model:

```bash
scripts/compare_models.py \
  --payload payload.bin \
  --corpus examples/carrier_train_v2.txt \
  --quality-text examples/carrier_heldout_v2.txt \
  --transformer-model transformer-torch.json \
  --shape-uniform-mix 0.90 \
  --temperature 1.75
```

Probability shaping is intentionally separate from the models. Defaults are a
no-op, while non-default shaping settings are written into the armour so decode
can reproduce the same distribution. This is the guardrail layer intended for
future Transformer-backed carriers.

The comparison harness reports both transport and language-quality metrics:

- Carrier chars and bits per carrier char.
- Average negative log likelihood on the corpus or `--quality-text`.
- Average entropy per model step.
- Average top-token probability.
- Deterministic greedy preview text.

Optional PyTorch training/export path:

```bash
scripts/train_transformer_torch.py \
  --data examples/carrier_train_v2.txt \
  --valid-data examples/carrier_heldout_v2.txt \
  --out transformer-torch.json \
  --block-size 16 \
  --d-model 16 \
  --ff-dim 32 \
  --epochs 12 \
  --learning-rate 0.006 \
  --max-train-tokens 0
```

PyTorch is only needed for this training exporter. The exported JSON model loads
through the normal dependency-free `TransformerLM` runtime.

Sweep shaping settings for an exported model:

```bash
scripts/sweep_shaping.py \
  --model transformer-torch.json \
  --payload payload.bin \
  --quality-text examples/carrier_heldout_v2.txt \
  --uniform-mixes 0.80,0.90,0.95 \
  --temperatures 1.25,1.75 \
  --min-entropy-bits 5.85 \
  --max-quality-chars 8000
```

On the current v2 corpus, the best small-grid setting was
`--shape-uniform-mix 0.80 --temperature 1.25`. Greedy preview still collapses,
so the sweep also reports encoded carrier preview and carrier diversity; the
actual LMCodec carrier is driven by payload bits rather than greedy decoding.
Use the full held-out file for final comparisons, and `--max-quality-chars` for
faster iterative pure-Python sweeps.

The pure-Python Transformer runtime caches token-position projections for
attention. On the current exported v2 model, building an 8000-character
held-out probability trace dropped from about 8.0 seconds to about 2.1 seconds,
and the bounded shaping sweep dropped from about 16 seconds to about 9 seconds.

A Karpathy `autoresearch`-style loop is a good future fit once held-out
evaluation is meaningful: let an agent propose corpus mixes, model sizes,
training settings, and shaping settings, then keep only experiments that improve
held-out NLL while preserving entropy, convergence, decode determinism, and
bits-per-character.

Current demo metrics for `bytes(range(256))`:

- Payload bytes: `256`
- Carrier chars: `358`
- Bits per carrier char: `5.989`
- Base64 baseline chars: `344`

Pinned Transformer fixture metrics for `bytes(range(256))` with
`--shape-uniform-mix 0.80 --temperature 1.25`:

- Payload bytes: `256`
- Carrier chars: `362`
- Bits per carrier char: `5.923`

## Golden V1

The current golden fixture is [tests/fixtures/golden_message_v1.txt](tests/fixtures/golden_message_v1.txt).

Fixed carrier pinned values:

- Model fingerprint: `d60583f4d741e42cb713b11c78b8ffc89cda1ee05eca522929bec8cbdb423be8`
- Message SHA256: `f53ec3604a378788b20cf6e0aadbfe441a063aa7ce1cea0bef9b1427cbd21e35`
- Payload SHA256: `40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880`

Order-1 n-gram carrier fixture:

- Model fixture: [tests/fixtures/ngram_model_v1.json](tests/fixtures/ngram_model_v1.json)
- Message fixture: [tests/fixtures/ngram_golden_message_v1.txt](tests/fixtures/ngram_golden_message_v1.txt)
- Model fingerprint: `b1cd62a9019b67e0a42913dac1dca09852b4931f09afa87bb8e62089fe184a3a`
- Message SHA256: `53c062a238764c72caa9dd338d37682ab350d7ace4251e9778ba13ae97d99512`
- Payload SHA256: `40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880`

Transformer carrier fixture:

- Model fixture: [tests/fixtures/transformer_model_v1.json](tests/fixtures/transformer_model_v1.json)
- Message fixture: [tests/fixtures/transformer_golden_message_v1.txt](tests/fixtures/transformer_golden_message_v1.txt)
- Settings: `SHAPE_UNIFORM_MIX=0.80; TEMPERATURE=1.25`
- Model fingerprint: `cfc75d7b54524f7a09a90454d89768aa4eb75b17546607c376760e2fc9d8f851`
- Message SHA256: `7713a0b7208462485f854ab58e5423f16c16360aeff524f1597ba49c840ad96b`
- Payload SHA256: `40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880`

To regenerate after intentional codec changes:

```bash
python3 scripts/generate_golden.py
```

## Recommended Build Order

1. Quantizer.
2. Range coder.
3. Codec with a fixed toy distribution.
4. Codec with a deterministic character n-gram model.
5. Armour and integrity checks.
6. Golden regression.
7. Probability shaping and experiment harness.
8. Transformer-backed LM experiments.
