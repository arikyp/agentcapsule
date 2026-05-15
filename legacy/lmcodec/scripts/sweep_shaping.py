#!/usr/bin/env python3
"""Sweep probability shaping settings for an exported Transformer model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.benchmarking import (  # noqa: E402
    error_record,
    git_commit,
    metrics_record,
    model_type,
    payload_info,
    utc_timestamp,
    write_json,
)
from lmcodec.codec import CodecSettings  # noqa: E402
from lmcodec.experiments import (  # noqa: E402
    ModelMetrics,
    build_probability_trace,
    evaluate_quality_trace,
    greedy_preview,
    measure_roundtrip,
)
from lmcodec.probability import ProbabilityShapeSettings  # noqa: E402
from lmcodec.transformer import TransformerLM  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", required=True)
    parser.add_argument("--payload", required=True)
    parser.add_argument("--quality-text", required=True)
    parser.add_argument("--uniform-mixes", default="0.75,0.85,0.90,0.95")
    parser.add_argument("--temperatures", default="1.25,1.50,1.75,2.00")
    parser.add_argument("--min-probs", default="0.0")
    parser.add_argument("--min-entropy-bits", type=float, default=5.85)
    parser.add_argument("--wrap", type=int, default=80)
    parser.add_argument("--max-steps", type=int, default=100000)
    parser.add_argument("--preview-chars", type=int, default=80)
    parser.add_argument("--max-quality-chars", type=int, help="evaluate only this many held-out characters")
    parser.add_argument("--json-out", help="write machine-readable benchmark results to this path")
    args = parser.parse_args(argv)

    model = TransformerLM.load(args.model)
    payload = Path(args.payload).read_bytes()
    payload_meta = payload_info(args.payload, payload)
    quality_text = Path(args.quality_text).read_text(encoding="utf-8")
    if args.max_quality_chars is not None:
        if args.max_quality_chars <= 0:
            print("max-quality-chars must be positive", file=sys.stderr)
            return 2
        quality_text = quality_text[: args.max_quality_chars]
    trace = build_probability_trace(model, quality_text)
    rows: list[tuple[float, float, float, float, ModelMetrics]] = []
    records: list[dict[str, object]] = []

    for uniform_mix in _float_list(args.uniform_mixes):
        for temperature in _float_list(args.temperatures):
            for min_prob in _float_list(args.min_probs):
                settings = CodecSettings(
                    shape=ProbabilityShapeSettings(
                        uniform_mix=uniform_mix,
                        temperature=temperature,
                        min_probability=min_prob,
                    )
                )
                try:
                    metrics = measure_roundtrip(
                        "transformer-export",
                        payload,
                        model,
                        settings=settings,
                        wrap=args.wrap,
                        max_steps=args.max_steps,
                        preview_chars=args.preview_chars,
                    )
                except Exception as exc:  # noqa: BLE001 - experiment script reports failed settings.
                    print(f"failed,{uniform_mix:.3f},{temperature:.3f},{min_prob:.6g},{exc}", file=sys.stderr)
                    records.append(
                        error_record(
                            name="transformer-export",
                            payload=payload_meta,
                            model_type_name=model_type(model),
                            model_fingerprint=model.fingerprint,
                            model_path=args.model,
                            settings=settings,
                            error=exc,
                        )
                    )
                    continue
                quality = evaluate_quality_trace(
                    trace,
                    settings=settings,
                    greedy_text=greedy_preview(model, settings=settings, max_chars=args.preview_chars),
                )
                metrics = ModelMetrics(
                    name=metrics.name,
                    payload_bytes=metrics.payload_bytes,
                    carrier_chars=metrics.carrier_chars,
                    armour_chars=metrics.armour_chars,
                    bits_per_carrier_char=metrics.bits_per_carrier_char,
                    model_fingerprint=metrics.model_fingerprint,
                    carrier_preview=metrics.carrier_preview,
                    encode_seconds=metrics.encode_seconds,
                    decode_seconds=metrics.decode_seconds,
                    quality=quality,
                    carrier_quality=metrics.carrier_quality,
                )
                diversity = preview_diversity(metrics.carrier_preview)
                score = _score(metrics, diversity, min_entropy_bits=args.min_entropy_bits)
                rows.append((score, uniform_mix, temperature, min_prob, metrics))
                record = metrics_record(
                    metrics=metrics,
                    payload=payload_meta,
                    model_type_name=model_type(model),
                    model_path=args.model,
                    settings=settings,
                )
                record["score"] = score
                record["carrier_diversity"] = diversity
                records.append(record)

    rows.sort(key=lambda row: row[0])
    _print_rows(rows)
    if args.json_out:
        write_json(
            args.json_out,
            {
                "schema_version": 1,
                "timestamp_utc": utc_timestamp(),
                "git_commit": git_commit(ROOT),
                "payload": payload_meta,
                "model": {
                    "type": model_type(model),
                    "fingerprint": model.fingerprint,
                    "path": args.model,
                },
                "quality_text": {
                    "path": args.quality_text,
                    "chars_evaluated": len(quality_text),
                    "max_quality_chars": args.max_quality_chars,
                },
                "sweep": {
                    "uniform_mixes": _float_list(args.uniform_mixes),
                    "temperatures": _float_list(args.temperatures),
                    "min_probs": _float_list(args.min_probs),
                    "min_entropy_bits": args.min_entropy_bits,
                    "max_steps": args.max_steps,
                    "wrap": args.wrap,
                },
                "results": records,
            },
        )
    return 0 if rows else 2


def preview_diversity(text: str, *, ngram: int = 3) -> float:
    if len(text) < ngram:
        return 0.0
    grams = [text[idx : idx + ngram] for idx in range(len(text) - ngram + 1)]
    return len(set(grams)) / len(grams)


def _score(metrics: ModelMetrics, diversity: float, *, min_entropy_bits: float) -> float:
    assert metrics.quality is not None
    entropy_penalty = max(0.0, min_entropy_bits - metrics.quality.avg_entropy_bits) * 4.0
    repetition_penalty = (1.0 - diversity) * 0.35
    carrier_penalty = max(0, metrics.carrier_chars - 358) * 0.005
    return metrics.quality.avg_nll_bits + entropy_penalty + repetition_penalty + carrier_penalty


def _print_rows(rows: list[tuple[float, float, float, float, ModelMetrics]]) -> None:
    print(
        "score,uniform_mix,temperature,min_prob,carrier_chars,bits_per_carrier_char,"
        "avg_nll_bits,avg_entropy_bits,avg_top_probability,carrier_diversity,carrier_preview,greedy_preview,model_fingerprint"
    )
    for score, uniform_mix, temperature, min_prob, metrics in rows:
        assert metrics.quality is not None
        diversity = preview_diversity(metrics.carrier_preview)
        print(
            f"{score:.3f},{uniform_mix:.3f},{temperature:.3f},{min_prob:.6g},"
            f"{metrics.carrier_chars},{metrics.bits_per_carrier_char:.3f},"
            f"{metrics.quality.avg_nll_bits:.3f},{metrics.quality.avg_entropy_bits:.3f},"
            f"{metrics.quality.avg_top_probability:.3f},{diversity:.3f},"
            f"{_csv_escape(metrics.carrier_preview)},{_csv_escape(metrics.quality.greedy_preview)},"
            f"{metrics.model_fingerprint}"
        )


def _float_list(text: str) -> list[float]:
    values = [float(item.strip()) for item in text.split(",") if item.strip()]
    if not values:
        raise ValueError("empty float list")
    return values


def _csv_escape(value: str) -> str:
    if any(char in value for char in ',\n"'):
        return '"' + value.replace('"', '""') + '"'
    return value


if __name__ == "__main__":
    raise SystemExit(main())
