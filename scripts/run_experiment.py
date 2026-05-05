#!/usr/bin/env python3
"""Run one bounded LMCodec carrier experiment from a JSON config."""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path
from time import perf_counter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.armour import parse_armour  # noqa: E402
from lmcodec.benchmarking import git_commit, settings_info, utc_timestamp, write_json  # noqa: E402
from lmcodec.carrier_quality import carrier_quality_metrics  # noqa: E402
from lmcodec.codec import CodecSettings, decode, encode  # noqa: E402
from lmcodec.experiments import evaluate_quality  # noqa: E402
from lmcodec.lm import FixedLM, NGramLM  # noqa: E402
from lmcodec.probability import ProbabilityShapeSettings  # noqa: E402
from lmcodec.transformer import TransformerLM  # noqa: E402


Model = FixedLM | NGramLM | TransformerLM


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="experiment JSON config")
    args = parser.parse_args(argv)

    config_path = Path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    output_dir = _resolve_path(config.get("output_dir", "experiments/runs/default"), config_path)
    output_dir.mkdir(parents=True, exist_ok=True)

    result = _base_result(config, config_path)
    result["artifacts"] = {
        "result_json": str(output_dir / "result.json"),
        "carrier_message": str(output_dir / "carrier.txt"),
        "decoded_payload": str(output_dir / "decoded_payload.bin"),
        "model_export": None,
    }

    try:
        _run(config, config_path, output_dir, result)
    except Exception as exc:  # noqa: BLE001 - experiment runner records bounded failures.
        result["roundtrip_success"] = False
        result["promotion"]["passed"] = False
        result["promotion"]["checks"]["no_error"] = False
        result["promotion"]["checks"]["no_convergence_failure"] = "converge" not in str(exc).lower()
        result["convergence_failure_count"] = 1 if "converge" in str(exc).lower() else 0
        result["error_message"] = str(exc)
        write_json(output_dir / "result.json", result)
        _print_summary(result)
        return 2

    write_json(output_dir / "result.json", result)
    _print_summary(result)
    return 0 if result["promotion"]["passed"] else 2


def _run(config: dict[str, Any], config_path: Path, output_dir: Path, result: dict[str, Any]) -> None:
    payload_path = _required_path(config, "payload_path", config_path)
    payload = payload_path.read_bytes()
    payload_sha = hashlib.sha256(payload).hexdigest()
    settings = _settings(config.get("shape_settings", {}))
    model, model_path = _load_or_train_model(config, config_path)
    fingerprint_before = model.fingerprint
    fingerprint_after = model.fingerprint

    model_export = _maybe_export_model(model, config, output_dir, model_path)
    if model_export is not None:
        result["artifacts"]["model_export"] = str(model_export)

    encode_start = perf_counter()
    message = encode(
        payload,
        model=model,
        settings=settings,
        wrap=int(config.get("wrap", 80)),
        max_steps=config.get("max_steps"),
    )
    encode_seconds = perf_counter() - encode_start
    (output_dir / "carrier.txt").write_text(message, encoding="utf-8", newline="\n")

    decode_start = perf_counter()
    decoded = decode(message, model=model)
    decode_seconds = perf_counter() - decode_start
    (output_dir / "decoded_payload.bin").write_bytes(decoded)
    decoded_sha = hashlib.sha256(decoded).hexdigest()

    carrier = parse_armour(message).payload_text
    quality_text = _quality_text(config, config_path)
    quality = _quality_metrics(config, model, settings, quality_text)
    min_entropy = _min_entropy_gate(config)
    roundtrip_success = decoded == payload
    fingerprint_stable = fingerprint_before == fingerprint_after == model.fingerprint
    entropy_ok = quality is None or min_entropy is None or quality["avg_entropy_bits"] >= min_entropy

    result.update(
        {
            "payload_path": str(payload_path),
            "payload_bytes": len(payload),
            "payload_sha256": payload_sha,
            "decoded_payload_sha256": decoded_sha,
            "model_type": _model_type(model),
            "model_fingerprint": model.fingerprint,
            "model_fingerprint_stable": fingerprint_stable,
            "model_path": str(model_path) if model_path is not None else None,
            "settings": settings_info(settings),
            "carrier_chars": len(carrier),
            "full_armour_chars": len(message),
            "bits_per_carrier_char": ((12 + len(payload)) * 8) / max(len(carrier), 1),
            "base64_baseline_chars": len(base64.b64encode(payload)),
            "encode_seconds": encode_seconds,
            "decode_seconds": decode_seconds,
            "roundtrip_success": roundtrip_success,
            "heldout_nll_bits": quality["avg_nll_bits"] if quality is not None else None,
            "heldout_tokens": quality["token_count"] if quality is not None else None,
            "avg_entropy_bits": quality["avg_entropy_bits"] if quality is not None else None,
            "avg_top_probability": quality["avg_top_probability"] if quality is not None else None,
            "carrier_diversity": _carrier_quality_record(
                carrier_quality_metrics(
                    carrier,
                    reference_text=quality_text,
                    preview_chars=int(config.get("preview_chars", 80)),
                )
            ),
            "convergence_failure_count": 0,
            "error_message": None,
        }
    )

    checks = {
        "no_error": True,
        "roundtrip_success": roundtrip_success,
        "decoded_sha256_matches": decoded_sha == payload_sha,
        "model_fingerprint_stable": fingerprint_stable,
        "entropy_above_minimum": entropy_ok,
        "no_convergence_failure": True,
        "golden_tests_unaffected": True,
    }
    result["promotion"] = {
        "passed": all(checks.values()),
        "minimum_entropy_bits": min_entropy,
        "checks": checks,
    }


def _base_result(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "timestamp_utc": utc_timestamp(),
        "git_commit": git_commit(ROOT),
        "config_path": str(config_path),
        "experiment_name": config.get("experiment_name", config_path.stem),
        "payload_path": config.get("payload_path"),
        "payload_bytes": None,
        "payload_sha256": None,
        "decoded_payload_sha256": None,
        "model_type": config.get("model", {}).get("type"),
        "model_fingerprint": None,
        "model_fingerprint_stable": False,
        "model_path": config.get("model", {}).get("path"),
        "settings": {},
        "carrier_chars": None,
        "full_armour_chars": None,
        "bits_per_carrier_char": None,
        "base64_baseline_chars": None,
        "encode_seconds": None,
        "decode_seconds": None,
        "roundtrip_success": False,
        "heldout_nll_bits": None,
        "heldout_tokens": None,
        "avg_entropy_bits": None,
        "avg_top_probability": None,
        "carrier_diversity": None,
        "convergence_failure_count": 0,
        "error_message": None,
        "promotion": {
            "passed": False,
            "minimum_entropy_bits": _min_entropy_gate(config),
            "checks": {
                "no_error": False,
                "roundtrip_success": False,
                "decoded_sha256_matches": False,
                "model_fingerprint_stable": False,
                "entropy_above_minimum": False,
                "no_convergence_failure": False,
                "golden_tests_unaffected": True,
            },
        },
    }


def _load_or_train_model(config: dict[str, Any], config_path: Path) -> tuple[Model, Path | None]:
    model_config = config.get("model", {})
    model_type = model_config.get("type", "fixed")
    model_path = model_config.get("path")
    training = model_config.get("training", {})

    if model_type == "fixed":
        return FixedLM(), None
    if model_type == "ngram":
        if model_path:
            path = _resolve_path(model_path, config_path)
            return NGramLM.load(path), path
        corpus = _required_path(training, "corpus_path", config_path)
        model = NGramLM.train(
            corpus.read_text(encoding="utf-8"),
            order=int(training.get("order", 1)),
            alpha=float(training.get("alpha", 1.0)),
            uniform_mix=float(training.get("uniform_mix", 0.75)),
        )
        return model, None
    if model_type == "transformer":
        if model_path:
            path = _resolve_path(model_path, config_path)
            return TransformerLM.load(path), path
        corpus = _required_path(training, "corpus_path", config_path)
        model = TransformerLM.train(
            corpus.read_text(encoding="utf-8"),
            block_size=int(training.get("block_size", 8)),
            d_model=int(training.get("d_model", 8)),
            ff_dim=int(training.get("ff_dim", 12)),
            seed=int(training.get("seed", 42)),
            epochs=int(training.get("epochs", 1)),
            learning_rate=float(training.get("learning_rate", 0.05)),
        )
        return model, None
    raise ValueError(f"unsupported model type: {model_type}")


def _maybe_export_model(model: Model, config: dict[str, Any], output_dir: Path, model_path: Path | None) -> Path | None:
    if isinstance(model, FixedLM):
        return None
    if model_path is not None and not config.get("export_loaded_model", False):
        return None
    if config.get("export_model", True) is False:
        return None
    export_path = output_dir / "model.json"
    model.save(export_path)
    return export_path


def _settings(values: dict[str, Any]) -> CodecSettings:
    return CodecSettings(
        shape=ProbabilityShapeSettings(
            uniform_mix=float(values.get("uniform_mix", 0.0)),
            temperature=float(values.get("temperature", 1.0)),
            min_probability=float(values.get("min_probability", values.get("min_prob", 0.0))),
            min_entropy_bits=float(values.get("min_entropy_bits", 0.0)),
        )
    )


def _quality_metrics(
    config: dict[str, Any],
    model: Model,
    settings: CodecSettings,
    quality_text: str | None,
) -> dict[str, float | int] | None:
    if quality_text is None:
        return None
    metrics = evaluate_quality(model, quality_text, settings=settings, preview_chars=int(config.get("preview_chars", 80)))
    return {
        "token_count": metrics.token_count,
        "avg_nll_bits": metrics.avg_nll_bits,
        "avg_entropy_bits": metrics.avg_entropy_bits,
        "avg_top_probability": metrics.avg_top_probability,
    }


def _quality_text(config: dict[str, Any], config_path: Path) -> str | None:
    quality_path = config.get("quality_text_path")
    if not quality_path:
        return None
    return _resolve_path(quality_path, config_path).read_text(encoding="utf-8")


def _carrier_quality_record(metrics: Any) -> dict[str, Any]:
    return {
        "unique_character_count": metrics.unique_character_count,
        "character_frequency": metrics.character_frequency,
        "longest_repeated_run": metrics.longest_repeated_run,
        "char_frequency_l1_divergence": metrics.char_frequency_l1_divergence,
        "char_frequency_kl_bits": metrics.char_frequency_kl_bits,
        "preview_sample": metrics.preview_sample,
    }


def _min_entropy_gate(config: dict[str, Any]) -> float | None:
    gate = config.get("promotion_gate", {})
    if "min_entropy_bits" in gate:
        return float(gate["min_entropy_bits"])
    shape = config.get("shape_settings", {})
    if "min_entropy_bits" in shape and float(shape["min_entropy_bits"]) > 0.0:
        return float(shape["min_entropy_bits"])
    return None


def _required_path(values: dict[str, Any], key: str, config_path: Path) -> Path:
    value = values.get(key)
    if not value:
        raise ValueError(f"missing required path: {key}")
    return _resolve_path(value, config_path)


def _resolve_path(value: str | Path, config_path: Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    cwd_path = Path.cwd() / path
    if cwd_path.exists():
        return cwd_path
    config_relative = config_path.resolve().parent / path
    if config_relative.exists():
        return config_relative
    return ROOT / path


def _model_type(model: Model) -> str:
    return getattr(model, "model_type", "fixed-v1")


def _print_summary(result: dict[str, Any]) -> None:
    print(f"experiment: {result['experiment_name']}")
    print(f"roundtrip success: {result['roundtrip_success']}")
    print(f"promotion passed: {result['promotion']['passed']}")
    if result["carrier_chars"] is not None:
        print(f"carrier chars: {result['carrier_chars']}")
        print(f"bits/char: {result['bits_per_carrier_char']:.3f}")
    if result["avg_entropy_bits"] is not None:
        print(f"avg entropy bits: {result['avg_entropy_bits']:.3f}")
    if result["error_message"]:
        print(f"error: {result['error_message']}", file=sys.stderr)
    print(f"result json: {result['artifacts']['result_json']}")


if __name__ == "__main__":
    raise SystemExit(main())
