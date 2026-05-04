# LMCodec Quickstart

LMCodec maps bytes into copy/paste-safe carrier text and decodes that text back
to the exact original bytes.

## Install

From the repository root:

```bash
python3 -m pip install -e .
```

This exposes the `lmcodec` command from `pyproject.toml`.

## Encode And Decode A File

Create a sample payload:

```bash
python3 - <<'PY'
from pathlib import Path
Path("/tmp/lmcodec-payload.bin").write_bytes(bytes(range(256)))
PY
```

Encode with the stable fixed carrier:

```bash
lmcodec encode --in /tmp/lmcodec-payload.bin --out /tmp/lmcodec-message.txt --wrap 80
```

Decode:

```bash
lmcodec decode --in /tmp/lmcodec-message.txt --out /tmp/lmcodec-output.bin
```

Verify:

```bash
cmp /tmp/lmcodec-payload.bin /tmp/lmcodec-output.bin
```

## Pinned Transformer Carrier

The Transformer carrier is experimental but pinned as a V1 fixture:

```bash
lmcodec encode \
  --model tests/fixtures/transformer_model_v1.json \
  --in /tmp/lmcodec-payload.bin \
  --out /tmp/lmcodec-transformer-message.txt \
  --wrap 80 \
  --shape-uniform-mix 0.80 \
  --temperature 1.25 \
  --max-steps 100000

lmcodec decode \
  --model tests/fixtures/transformer_model_v1.json \
  --in /tmp/lmcodec-transformer-message.txt \
  --out /tmp/lmcodec-transformer-output.bin

cmp /tmp/lmcodec-payload.bin /tmp/lmcodec-transformer-output.bin
```

## Verify The Release

Run:

```bash
sh scripts/release_check.sh
```

For lower-level V1 fixture verification:

```bash
sh scripts/verify_v1.sh
```
