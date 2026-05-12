#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

python3 scripts/generate_golden.py
sh scripts/demo_roundtrip.sh
sh scripts/demo_compare.sh
sh scripts/demo_transformer.sh
PYTHONPATH=src python3 -m unittest discover -s tests
python3 -m py_compile \
  src/lmcodec/*.py \
  scripts/build_carrier_corpus.py \
  scripts/compare_models.py \
  scripts/generate_golden.py \
  scripts/split_corpus.py \
  scripts/sweep_shaping.py \
  scripts/train_transformer_torch.py

echo "Agent Capsule V1 verification ok"
