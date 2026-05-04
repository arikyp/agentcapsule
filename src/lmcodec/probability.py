"""Deterministic probability shaping before range-coder quantization."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite, log2

from lmcodec.errors import LMCodecError


@dataclass(frozen=True)
class ProbabilityShapeSettings:
    """Policy for flattening model distributions before quantization."""

    uniform_mix: float = 0.0
    temperature: float = 1.0
    min_probability: float = 0.0
    min_entropy_bits: float = 0.0

    def as_header(self) -> dict[str, str]:
        values: dict[str, str] = {}
        if self.uniform_mix != 0.0:
            values["SHAPE_UNIFORM_MIX"] = _format_float(self.uniform_mix)
        if self.temperature != 1.0:
            values["TEMPERATURE"] = _format_float(self.temperature)
        if self.min_probability != 0.0:
            values["MIN_PROB"] = _format_float(self.min_probability)
        if self.min_entropy_bits != 0.0:
            values["MIN_ENTROPY_BITS"] = _format_float(self.min_entropy_bits)
        return values

    @classmethod
    def from_header(cls, values: dict[str, str]) -> ProbabilityShapeSettings:
        return cls(
            uniform_mix=_read_float(values, "SHAPE_UNIFORM_MIX", 0.0),
            temperature=_read_float(values, "TEMPERATURE", 1.0),
            min_probability=_read_float(values, "MIN_PROB", 0.0),
            min_entropy_bits=_read_float(values, "MIN_ENTROPY_BITS", 0.0),
        )


def shape_probabilities(
    probs: list[float] | tuple[float, ...],
    settings: ProbabilityShapeSettings | None = None,
) -> tuple[float, ...]:
    """Return a normalized, deterministic distribution safe for coding."""

    settings = settings or ProbabilityShapeSettings()
    _validate_shape_settings(settings)
    base = _normalize(probs)

    if settings.temperature != 1.0:
        inv_temperature = 1.0 / settings.temperature
        base = _normalize(tuple(prob**inv_temperature for prob in base))

    vocab_size = len(base)
    uniform = 1.0 / vocab_size
    shaped = tuple(
        (1.0 - settings.uniform_mix) * prob + settings.uniform_mix * uniform
        for prob in base
    )

    if settings.min_probability > 0.0:
        shaped = _normalize(tuple(max(prob, settings.min_probability) for prob in shaped))

    entropy = entropy_bits(shaped)
    if entropy + 1e-12 < settings.min_entropy_bits:
        raise LMCodecError("probability distribution below entropy guard")

    return shaped


def entropy_bits(probs: list[float] | tuple[float, ...]) -> float:
    total = 0.0
    for prob in _normalize(probs):
        total -= prob * log2(prob)
    return total


def _normalize(probs: list[float] | tuple[float, ...]) -> tuple[float, ...]:
    if not probs:
        raise LMCodecError("probability distribution is empty")
    cleaned = tuple(prob if isfinite(prob) and prob > 0.0 else 0.0 for prob in probs)
    total = sum(cleaned)
    if total <= 0.0:
        return tuple(1.0 / len(cleaned) for _ in cleaned)
    return tuple(prob / total for prob in cleaned)


def _validate_shape_settings(settings: ProbabilityShapeSettings) -> None:
    if not 0.0 <= settings.uniform_mix <= 1.0:
        raise LMCodecError("invalid settings")
    if not isfinite(settings.temperature) or settings.temperature <= 0.0:
        raise LMCodecError("invalid settings")
    if not isfinite(settings.min_probability) or settings.min_probability < 0.0:
        raise LMCodecError("invalid settings")
    if not isfinite(settings.min_entropy_bits) or settings.min_entropy_bits < 0.0:
        raise LMCodecError("invalid settings")


def _read_float(values: dict[str, str], key: str, default: float) -> float:
    try:
        return float(values.get(key, default))
    except ValueError as exc:
        raise LMCodecError("invalid settings") from exc


def _format_float(value: float) -> str:
    return f"{value:.17g}"
