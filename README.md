# LMCodec

[![CI](https://github.com/arikyp/lmcodec/actions/workflows/ci.yml/badge.svg)](https://github.com/arikyp/lmcodec/actions/workflows/ci.yml)

LMCodec is an experimental deterministic codec that maps arbitrary bytes into
copy/paste-safe text using language-model probability distributions as the
carrier shape.

The codec uses a language model as the probability source and a deterministic
range coder as the reversible bit-to-symbol mapping layer. Decode repeats the
same model, shaping, and quantization steps to recover the original framed
payload bytes.

## Current Status

LMCodec V1 is a research prototype.

- The fixed 64-symbol carrier is the stable default path.
- The order-1 n-gram carrier is experimental, deterministic, and pinned as a
  V1 fixture.
- The Transformer-style carrier is experimental, deterministic, and pinned as a
  V1 fixture.
- Golden fixtures are committed for fixed, n-gram, and Transformer carriers.
- Runtime encode/decode is dependency-free Python.

## What Works

- Byte-perfect encode/decode roundtrip for the tested payload sizes and demos.
- Deterministic output for identical payload, model, and settings.
- Model fingerprint checks before decode.
- Copy/paste armour with version, model fingerprint, and settings.
- CLI file encode/decode.
- CRC32 corruption detection inside the payload frame.
- Unit, stress, golden, and end-to-end verification tests.

## What Does Not Yet Work

- Semantically meaningful prose generation.
- Production privacy or encryption.
- Steganography-grade secrecy.
- Compression superiority over base64.
- Large-file archival confidence.
- GPU-scale model training in the runtime path.

## Quickstart

Use a virtual environment for local development:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e .
```

Encode and decode a file with the default fixed carrier:

```bash
PYTHONPATH=src python3 -m lmcodec.cli encode --in payload.bin --out message.txt --wrap 80
PYTHONPATH=src python3 -m lmcodec.cli decode --in message.txt --out recovered.bin
cmp payload.bin recovered.bin
```

Train and use a deterministic order-1 n-gram carrier:

```bash
PYTHONPATH=src python3 -m lmcodec.cli train \
  --data examples/carrier_train_v1.txt \
  --out ngram.json \
  --order 1 \
  --uniform-mix 0.75
PYTHONPATH=src python3 -m lmcodec.cli encode \
  --model ngram.json \
  --in payload.bin \
  --out message.txt \
  --wrap 80
PYTHONPATH=src python3 -m lmcodec.cli decode \
  --model ngram.json \
  --in message.txt \
  --out recovered.bin
cmp payload.bin recovered.bin
```

Use the pinned experimental Transformer fixture:

```bash
PYTHONPATH=src python3 -m lmcodec.cli encode \
  --model tests/fixtures/transformer_model_v1.json \
  --in payload.bin \
  --out message.txt \
  --wrap 80 \
  --shape-uniform-mix 0.80 \
  --temperature 1.25 \
  --max-steps 100000
PYTHONPATH=src python3 -m lmcodec.cli decode \
  --model tests/fixtures/transformer_model_v1.json \
  --in message.txt \
  --out recovered.bin
cmp payload.bin recovered.bin
```

## Architecture

LMCodec has five core layers:

- Frame: wraps the payload as `magic || payload_len || crc32 || payload`.
- Range coder: provides the reversible bit-to-symbol mapping.
- LM probabilities: provide the next-token carrier distribution.
- Quantizer: converts floating-point probabilities into deterministic integer
  CDFs for range coding.
- Armour: stores carrier text with version, model fingerprint, and settings in
  a copy/paste-safe text block.

Encoding:

```text
payload bytes
  -> binary frame
  -> framed bits
  -> source RangeDecoder over framed bits
  -> LM probabilities + shaping + quantization
  -> carrier token choices
  -> mirror RangeEncoder stopping check
  -> armoured text
```

Decoding:

```text
armoured text
  -> parse and check model fingerprint
  -> carrier tokens
  -> same LM probabilities + shaping + quantization
  -> RangeEncoder reconstructs framed bits
  -> frame parser validates magic, length, and CRC32
  -> payload bytes
```

The stopping condition is intentionally conservative. Range decoders use
lookahead, so encode does not stop based on a naive "all bits consumed" rule.
Instead, LMCodec keeps a mirror range encoder and stops only when its finalized
preview has the framed payload bits as a prefix.

## Verification

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

## Demo And Experiment Scripts

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

Create deterministic carrier corpora and train/held-out splits:

```bash
scripts/build_carrier_corpus.py \
  --out examples/carrier_corpus_v2.txt \
  --lines 5000 \
  --seed 42 \
  --domain mixed
scripts/split_corpus.py \
  --input examples/carrier_corpus_v2.txt \
  --train-out examples/carrier_train_v2.txt \
  --heldout-out examples/carrier_heldout_v2.txt \
  --heldout-ratio 0.20 \
  --filter-vocab
```

Compare models with optional benchmark JSON:

```bash
scripts/compare_models.py \
  --payload payload.bin \
  --corpus examples/carrier_train_v2.txt \
  --quality-text examples/carrier_heldout_v2.txt \
  --json-out benchmark.json
```

Run a bounded V2 experiment config:

```bash
scripts/run_experiment.py experiments/configs/example_fixed.json
```

Optional PyTorch training/export is available in
`scripts/train_transformer_torch.py`. PyTorch is only needed for that exporter;
the exported JSON model loads through the dependency-free `TransformerLM`
runtime.

## Research Notes

Probability shaping is intentionally separate from the models. Defaults are a
no-op, while non-default shaping settings are written into the armour so decode
can reproduce the same distribution. Uniform mixing and temperature are
guardrails for keeping model distributions usable by the range coder; they are
not a claim of natural language quality.

Greedy previews are useful diagnostics, but they are not representative of
encoded carrier text. The actual LMCodec carrier is selected by payload bits
through the range coder under the model distribution.

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

## Documentation

- [docs/ALGORITHM.md](docs/ALGORITHM.md): core reversible mapping.
- [docs/IMPLEMENTATION_PLAN.md](docs/IMPLEMENTATION_PLAN.md): implementation
  milestones and design notes.
- [docs/V1_RELEASE.md](docs/V1_RELEASE.md): V1 checkpoint and pinned artifact
  details.
- [docs/LIMITATIONS.md](docs/LIMITATIONS.md): current boundaries and non-goals.
- [docs/QUICKSTART.md](docs/QUICKSTART.md): installed CLI usage.
- [docs/BENCHMARKING.md](docs/BENCHMARKING.md): structured benchmark JSON.
- [docs/EXPERIMENTS.md](docs/EXPERIMENTS.md): bounded V2 experiment runner.
- [docs/V2_BASELINE.md](docs/V2_BASELINE.md): V2 baseline metrics and first
  candidate runs.
- [docs/V2_EXPERIMENT_PROTOCOL.md](docs/V2_EXPERIMENT_PROTOCOL.md): V2
  promotion gates and experiment rules.
- [docs/V2_AUTOAGENT.md](docs/V2_AUTOAGENT.md): autoagent role and guardrails
  for bounded V2 research.
- [docs/V2_CANDIDATE_REPORT_TEMPLATE.md](docs/V2_CANDIDATE_REPORT_TEMPLATE.md):
  report shape for reviewed V2 candidates.
- [docs/V2_CHECKPOINT.md](docs/V2_CHECKPOINT.md): V2 research checkpoint,
  matrix ranking, and merge recommendation.
- [docs/V2_LARGE_PAYLOAD_REAL_CORPUS_STRESS.md](docs/V2_LARGE_PAYLOAD_REAL_CORPUS_STRESS.md):
  next stress lane for larger payloads and real-ish corpora.
- [docs/V2_LARGE_PAYLOAD_STRESS_RESULTS.md](docs/V2_LARGE_PAYLOAD_STRESS_RESULTS.md):
  capped large-payload stress results and runtime finding.
- [docs/V2_SIZE_LADDER.md](docs/V2_SIZE_LADDER.md): scaled payload ladder for
  locating the current runtime knee.
- [docs/V2_SIZE_LADDER_RESULTS.md](docs/V2_SIZE_LADDER_RESULTS.md): observed
  32KB/64KB runtime boundary.
- [docs/V2_SPRINT_1.md](docs/V2_SPRINT_1.md): first V2 candidate stress
  sprint.
- [docs/V2_SPRINT_2.md](docs/V2_SPRINT_2.md): first autoagent-safe
  comparison sprint.
- [docs/V2_SPRINT_3.md](docs/V2_SPRINT_3.md): order-3 candidate stress
  sprint.
- [docs/V2_CANDIDATE_ORDER3.md](docs/V2_CANDIDATE_ORDER3.md): current order-3
  candidate report.
- [docs/V2_CANDIDATE_ORDER3_SHAPED.md](docs/V2_CANDIDATE_ORDER3_SHAPED.md):
  shaped order-3 candidate report.
- [docs/V2_CANDIDATE_ORDER2_SAFETY.md](docs/V2_CANDIDATE_ORDER2_SAFETY.md):
  order-2 safety fallback report.
- [docs/V2_CANDIDATE_TRANSFORMER_FIXTURE.md](docs/V2_CANDIDATE_TRANSFORMER_FIXTURE.md):
  Transformer fixture candidate report.
- [docs/CARRIER_QUALITY.md](docs/CARRIER_QUALITY.md): carrier quality metrics
  and trade-offs.
- [docs/TESTING.md](docs/TESTING.md): stress/property test strategy.
- [schemas/benchmark_result_v1.json](schemas/benchmark_result_v1.json):
  benchmark JSON schema contract.
- [CHANGELOG.md](CHANGELOG.md): release notes.
- [LICENSE](LICENSE): current license status.

## Golden V1 Fixtures

All golden fixtures use payload `bytes(range(256))`.

Payload SHA256:

```text
40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880
```

Fixed carrier:

- Message fixture: [tests/fixtures/golden_message_v1.txt](tests/fixtures/golden_message_v1.txt)
- Model fingerprint: `d60583f4d741e42cb713b11c78b8ffc89cda1ee05eca522929bec8cbdb423be8`
- Message SHA256: `f53ec3604a378788b20cf6e0aadbfe441a063aa7ce1cea0bef9b1427cbd21e35`

Order-1 n-gram carrier fixture:

- Model fixture: [tests/fixtures/ngram_model_v1.json](tests/fixtures/ngram_model_v1.json)
- Message fixture: [tests/fixtures/ngram_golden_message_v1.txt](tests/fixtures/ngram_golden_message_v1.txt)
- Model fingerprint: `b1cd62a9019b67e0a42913dac1dca09852b4931f09afa87bb8e62089fe184a3a`
- Message SHA256: `53c062a238764c72caa9dd338d37682ab350d7ace4251e9778ba13ae97d99512`

Transformer carrier fixture:

- Model fixture: [tests/fixtures/transformer_model_v1.json](tests/fixtures/transformer_model_v1.json)
- Message fixture: [tests/fixtures/transformer_golden_message_v1.txt](tests/fixtures/transformer_golden_message_v1.txt)
- Settings: `SHAPE_UNIFORM_MIX=0.80; TEMPERATURE=1.25`
- Model fingerprint: `cfc75d7b54524f7a09a90454d89768aa4eb75b17546607c376760e2fc9d8f851`
- Message SHA256: `7713a0b7208462485f854ab58e5423f16c16360aeff524f1597ba49c840ad96b`

Regenerate golden fixtures only after intentional codec changes:

```bash
python3 scripts/generate_golden.py
```
