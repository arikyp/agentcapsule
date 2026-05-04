#!/usr/bin/env python3
"""Generate the current V1 golden message fixture."""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from lmcodec.codec import CodecSettings, decode, encode  # noqa: E402
from lmcodec.lm import FixedLM, NGramLM  # noqa: E402
from lmcodec.probability import ProbabilityShapeSettings  # noqa: E402
from lmcodec.transformer import TransformerLM  # noqa: E402

FIXTURE_DIR = ROOT / "tests" / "fixtures"
EXAMPLES_DIR = ROOT / "examples"
FIXED_GOLDEN_MESSAGE = FIXTURE_DIR / "golden_message_v1.txt"
NGRAM_MODEL = FIXTURE_DIR / "ngram_model_v1.json"
NGRAM_GOLDEN_MESSAGE = FIXTURE_DIR / "ngram_golden_message_v1.txt"
TRANSFORMER_MODEL = FIXTURE_DIR / "transformer_model_v1.json"
TRANSFORMER_GOLDEN_MESSAGE = FIXTURE_DIR / "transformer_golden_message_v1.txt"
CORPUS = EXAMPLES_DIR / "carrier_corpus_v1.txt"
PAYLOAD = bytes(range(256))
TRANSFORMER_SETTINGS = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.80, temperature=1.25))


def main() -> int:
    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)

    fixed_model = FixedLM()
    fixed_message = _write_golden(FIXED_GOLDEN_MESSAGE, fixed_model)

    corpus_text = CORPUS.read_text(encoding="utf-8")
    ngram_model = NGramLM.train(corpus_text, order=1, alpha=1.0, uniform_mix=0.75)
    ngram_model.save(NGRAM_MODEL)
    ngram_message = _write_golden(NGRAM_GOLDEN_MESSAGE, ngram_model)

    transformer_model = TransformerLM.load(TRANSFORMER_MODEL)
    transformer_message = _write_golden(
        TRANSFORMER_GOLDEN_MESSAGE,
        transformer_model,
        settings=TRANSFORMER_SETTINGS,
        max_steps=100000,
    )

    print("[fixed]")
    _print_values(fixed_model.fingerprint, fixed_message)
    print(f"message path: {FIXED_GOLDEN_MESSAGE}")
    print()
    print("[ngram-order1]")
    _print_values(ngram_model.fingerprint, ngram_message)
    print(f"model path: {NGRAM_MODEL}")
    print(f"message path: {NGRAM_GOLDEN_MESSAGE}")
    print()
    print("[transformer]")
    _print_values(transformer_model.fingerprint, transformer_message)
    print(f"model path: {TRANSFORMER_MODEL}")
    print(f"message path: {TRANSFORMER_GOLDEN_MESSAGE}")
    return 0


def _write_golden(
    path: Path,
    model: FixedLM | NGramLM | TransformerLM,
    *,
    settings: CodecSettings | None = None,
    max_steps: int | None = None,
) -> str:
    message = encode(PAYLOAD, model=model, settings=settings, wrap=80, max_steps=max_steps)
    canonical = message.replace("\r\n", "\n").replace("\r", "\n")
    decoded = decode(canonical, model=model)
    if decoded != PAYLOAD:
        raise SystemExit("golden decode failed")
    path.write_text(canonical, encoding="utf-8", newline="\n")
    return canonical


def _print_values(model_fingerprint: str, message: str) -> None:
    print(f"model fingerprint: {model_fingerprint}")
    print(f"message sha256: {hashlib.sha256(message.encode('utf-8')).hexdigest()}")
    print(f"payload sha256: {hashlib.sha256(PAYLOAD).hexdigest()}")


if __name__ == "__main__":
    raise SystemExit(main())
