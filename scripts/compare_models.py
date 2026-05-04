#!/usr/bin/env python3
"""Compare LMCodec carrier models with one payload."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.codec import CodecSettings  # noqa: E402
from lmcodec.experiments import ModelMetrics, measure_roundtrip  # noqa: E402
from lmcodec.lm import FixedLM, NGramLM  # noqa: E402
from lmcodec.probability import ProbabilityShapeSettings  # noqa: E402
from lmcodec.transformer import TransformerLM  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--payload", required=True, help="binary payload to encode/decode")
    parser.add_argument("--corpus", help="training text for an order-1 n-gram model")
    parser.add_argument("--quality-text", help="held-out text for quality metrics; defaults to --corpus")
    parser.add_argument("--include-transformer", action="store_true")
    parser.add_argument("--transformer-model", help="pretrained TransformerLM JSON to include")
    parser.add_argument("--uniform-mix", type=float, default=0.75)
    parser.add_argument("--block-size", type=int, default=16)
    parser.add_argument("--d-model", type=int, default=16)
    parser.add_argument("--ff-dim", type=int, default=32)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--shape-uniform-mix", type=float, default=0.0)
    parser.add_argument("--temperature", type=float, default=1.0)
    parser.add_argument("--min-prob", type=float, default=0.0)
    parser.add_argument("--min-entropy-bits", type=float, default=0.0)
    parser.add_argument("--wrap", type=int, default=80)
    parser.add_argument("--max-steps", type=int)
    parser.add_argument("--preview-chars", type=int, default=80)
    args = parser.parse_args(argv)

    payload = Path(args.payload).read_bytes()
    quality_text = _read_quality_text(args.quality_text, args.corpus)
    settings = CodecSettings(
        shape=ProbabilityShapeSettings(
            uniform_mix=args.shape_uniform_mix,
            temperature=args.temperature,
            min_probability=args.min_prob,
            min_entropy_bits=args.min_entropy_bits,
        )
    )

    results = [
        measure_roundtrip(
            "fixed",
            payload,
            FixedLM(),
            settings=settings,
            wrap=args.wrap,
            max_steps=args.max_steps,
            quality_text=quality_text,
            preview_chars=args.preview_chars,
        )
    ]
    if args.corpus:
        text = Path(args.corpus).read_text(encoding="utf-8")
        model = NGramLM.train(text, order=1, uniform_mix=args.uniform_mix)
        results.append(
            measure_roundtrip(
                "ngram-order-1",
                payload,
                model,
                settings=settings,
                wrap=args.wrap,
                max_steps=args.max_steps,
                quality_text=quality_text,
                preview_chars=args.preview_chars,
            )
        )
        if args.include_transformer or args.transformer_model:
            if args.transformer_model:
                transformer = TransformerLM.load(args.transformer_model)
                name = "transformer-export"
            else:
                transformer = TransformerLM.train(
                    text,
                    block_size=args.block_size,
                    d_model=args.d_model,
                    ff_dim=args.ff_dim,
                    epochs=args.epochs,
                    learning_rate=args.learning_rate,
                )
                name = "transformer-rf"
            results.append(
                measure_roundtrip(
                    name,
                    payload,
                    transformer,
                    settings=settings,
                    wrap=args.wrap,
                    max_steps=args.max_steps,
                    quality_text=quality_text,
                    preview_chars=args.preview_chars,
                )
            )
    elif args.transformer_model:
        transformer = TransformerLM.load(args.transformer_model)
        results.append(
            measure_roundtrip(
                "transformer-export",
                payload,
                transformer,
                settings=settings,
                wrap=args.wrap,
                max_steps=args.max_steps,
                quality_text=quality_text,
                preview_chars=args.preview_chars,
            )
        )

    _print_results(results)
    return 0


def _print_results(results: list[ModelMetrics]) -> None:
    print(
        "model,payload_bytes,carrier_chars,armour_chars,bits_per_carrier_char,"
        "quality_tokens,avg_nll_bits,avg_entropy_bits,avg_top_probability,carrier_preview,greedy_preview,model_fingerprint"
    )
    for item in results:
        quality_tokens = ""
        avg_nll_bits = ""
        avg_entropy_bits = ""
        avg_top_probability = ""
        greedy = ""
        if item.quality is not None:
            quality_tokens = str(item.quality.token_count)
            avg_nll_bits = f"{item.quality.avg_nll_bits:.3f}"
            avg_entropy_bits = f"{item.quality.avg_entropy_bits:.3f}"
            avg_top_probability = f"{item.quality.avg_top_probability:.3f}"
            greedy = _csv_escape(item.quality.greedy_preview)
        print(
            f"{item.name},{item.payload_bytes},{item.carrier_chars},"
            f"{item.armour_chars},{item.bits_per_carrier_char:.3f},"
            f"{quality_tokens},{avg_nll_bits},{avg_entropy_bits},{avg_top_probability},"
            f"{_csv_escape(item.carrier_preview)},{greedy},{item.model_fingerprint}"
        )


def _read_quality_text(path: str | None, corpus: str | None) -> str | None:
    source = path or corpus
    if source is None:
        return None
    return Path(source).read_text(encoding="utf-8")


def _csv_escape(value: str) -> str:
    if any(char in value for char in ',\n"'):
        return '"' + value.replace('"', '""') + '"'
    return value


if __name__ == "__main__":
    raise SystemExit(main())
