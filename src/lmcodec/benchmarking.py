"""JSON helpers for reproducible LMCodec benchmark output."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any

from lmcodec.codec import CodecSettings
from lmcodec.experiments import ModelMetrics
from lmcodec.lm import FixedLM, NGramLM
from lmcodec.transformer import TransformerLM


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def git_commit(root: Path) -> str | None:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=2.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    commit = result.stdout.strip()
    return commit or None


def payload_info(path: str | Path, payload: bytes) -> dict[str, Any]:
    return {
        "path": str(path),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "base64_baseline_chars": len(base64.b64encode(payload)),
    }


def settings_info(settings: CodecSettings) -> dict[str, Any]:
    return {
        "total": settings.total,
        "topk": settings.topk,
        "shape": {
            "uniform_mix": settings.shape.uniform_mix,
            "temperature": settings.shape.temperature,
            "min_probability": settings.shape.min_probability,
            "min_entropy_bits": settings.shape.min_entropy_bits,
        },
    }


def model_type(model: FixedLM | NGramLM | TransformerLM) -> str:
    return getattr(model, "model_type", "fixed-v1")


def metrics_record(
    *,
    metrics: ModelMetrics,
    payload: dict[str, Any],
    model_type_name: str,
    model_path: str | None,
    settings: CodecSettings,
    convergence_failure_count: int = 0,
) -> dict[str, Any]:
    quality = metrics.quality
    carrier_quality = metrics.carrier_quality
    return {
        "name": metrics.name,
        "payload_path": payload["path"],
        "payload_bytes": payload["bytes"],
        "payload_sha256": payload["sha256"],
        "model_type": model_type_name,
        "model_fingerprint": metrics.model_fingerprint,
        "model_path": model_path,
        "settings": settings_info(settings),
        "carrier_chars": metrics.carrier_chars,
        "full_armour_chars": metrics.armour_chars,
        "bits_per_carrier_char": metrics.bits_per_carrier_char,
        "base64_baseline_chars": payload["base64_baseline_chars"],
        "encode_seconds": metrics.encode_seconds,
        "decode_seconds": metrics.decode_seconds,
        "roundtrip_success": True,
        "heldout_nll_bits": quality.avg_nll_bits if quality is not None else None,
        "heldout_tokens": quality.token_count if quality is not None else None,
        "avg_entropy_bits": quality.avg_entropy_bits if quality is not None else None,
        "avg_top_probability": quality.avg_top_probability if quality is not None else None,
        "carrier_quality": _carrier_quality_record(carrier_quality),
        "convergence_failure_count": convergence_failure_count,
        "error_message": None,
    }


def error_record(
    *,
    name: str,
    payload: dict[str, Any],
    model_type_name: str,
    model_fingerprint: str | None,
    model_path: str | None,
    settings: CodecSettings,
    error: BaseException,
) -> dict[str, Any]:
    message = str(error)
    return {
        "name": name,
        "payload_path": payload["path"],
        "payload_bytes": payload["bytes"],
        "payload_sha256": payload["sha256"],
        "model_type": model_type_name,
        "model_fingerprint": model_fingerprint,
        "model_path": model_path,
        "settings": settings_info(settings),
        "carrier_chars": None,
        "full_armour_chars": None,
        "bits_per_carrier_char": None,
        "base64_baseline_chars": payload["base64_baseline_chars"],
        "encode_seconds": None,
        "decode_seconds": None,
        "roundtrip_success": False,
        "heldout_nll_bits": None,
        "heldout_tokens": None,
        "avg_entropy_bits": None,
        "avg_top_probability": None,
        "carrier_quality": None,
        "convergence_failure_count": 1 if "converge" in message.lower() else 0,
        "error_message": message,
    }


def write_json(path: str | Path, document: dict[str, Any]) -> None:
    Path(path).write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _carrier_quality_record(metrics: Any) -> dict[str, Any] | None:
    if metrics is None:
        return None
    return {
        "unique_character_count": metrics.unique_character_count,
        "character_frequency": metrics.character_frequency,
        "longest_repeated_run": metrics.longest_repeated_run,
        "char_frequency_l1_divergence": metrics.char_frequency_l1_divergence,
        "char_frequency_kl_bits": metrics.char_frequency_kl_bits,
        "preview_sample": metrics.preview_sample,
    }
