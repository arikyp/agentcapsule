"""Small experiment helpers for comparing carrier models."""

from __future__ import annotations

from dataclasses import dataclass
from math import log2
from time import perf_counter

from lmcodec.carrier_quality import CarrierQualityMetrics, carrier_quality_metrics
from lmcodec.codec import CodecSettings, decode, encode
from lmcodec.lm import FixedLM, NGramLM
from lmcodec.probability import ProbabilityShapeSettings, entropy_bits, shape_probabilities
from lmcodec.transformer import TransformerLM


@dataclass(frozen=True)
class ModelMetrics:
    name: str
    payload_bytes: int
    carrier_chars: int
    armour_chars: int
    bits_per_carrier_char: float
    model_fingerprint: str
    carrier_preview: str
    encode_seconds: float = 0.0
    decode_seconds: float = 0.0
    quality: QualityMetrics | None = None
    carrier_quality: CarrierQualityMetrics | None = None


@dataclass(frozen=True)
class QualityMetrics:
    token_count: int
    avg_nll_bits: float
    avg_entropy_bits: float
    avg_top_probability: float
    greedy_preview: str


@dataclass(frozen=True)
class ProbabilityTrace:
    targets: tuple[int, ...]
    probabilities: tuple[tuple[float, ...], ...]

    @property
    def token_count(self) -> int:
        return len(self.targets)


def measure_roundtrip(
    name: str,
    payload: bytes,
    model: FixedLM | NGramLM | TransformerLM,
    *,
    settings: CodecSettings | None = None,
    wrap: int = 0,
    max_steps: int | None = None,
    quality_text: str | None = None,
    preview_chars: int = 80,
) -> ModelMetrics:
    encode_start = perf_counter()
    message = encode(payload, model=model, settings=settings, wrap=wrap, max_steps=max_steps)
    encode_seconds = perf_counter() - encode_start
    decode_start = perf_counter()
    recovered = decode(message, model=model)
    decode_seconds = perf_counter() - decode_start
    if recovered != payload:
        raise AssertionError("roundtrip mismatch")

    carrier_text = _carrier_text(message)
    carrier_chars = len(carrier_text)
    payload_bits = (12 + len(payload)) * 8
    return ModelMetrics(
        name=name,
        payload_bytes=len(payload),
        carrier_chars=carrier_chars,
        armour_chars=len(message),
        bits_per_carrier_char=payload_bits / max(carrier_chars, 1),
        model_fingerprint=model.fingerprint,
        carrier_preview=carrier_text[:preview_chars],
        encode_seconds=encode_seconds,
        decode_seconds=decode_seconds,
        quality=evaluate_quality(model, quality_text, settings=settings, preview_chars=preview_chars) if quality_text else None,
        carrier_quality=carrier_quality_metrics(carrier_text, reference_text=quality_text, preview_chars=preview_chars),
    )


def evaluate_quality(
    model: FixedLM | NGramLM | TransformerLM,
    text: str,
    *,
    settings: CodecSettings | None = None,
    preview_chars: int = 80,
) -> QualityMetrics:
    settings = settings or CodecSettings()
    trace = build_probability_trace(model, text)
    return evaluate_quality_trace(trace, settings=settings, greedy_text=greedy_preview(model, settings=settings, max_chars=preview_chars))


def build_probability_trace(
    model: FixedLM | NGramLM | TransformerLM,
    text: str,
) -> ProbabilityTrace:
    state = model.init_state()
    targets: list[int] = []
    probabilities: list[tuple[float, ...]] = []

    for char in text:
        try:
            token_id = model.token_to_id(char)
        except ValueError:
            continue
        probabilities.append(tuple(model.step_probs(state)))
        targets.append(token_id)
        model.advance(state, token_id)

    if not targets:
        raise ValueError("quality text has no characters in model vocab")

    return ProbabilityTrace(targets=tuple(targets), probabilities=tuple(probabilities))


def evaluate_quality_trace(
    trace: ProbabilityTrace,
    *,
    settings: CodecSettings | None = None,
    greedy_text: str = "",
) -> QualityMetrics:
    settings = settings or CodecSettings()
    shape = settings.shape or ProbabilityShapeSettings()
    nll = 0.0
    entropy = 0.0
    top_probability = 0.0

    for token_id, raw_probs in zip(trace.targets, trace.probabilities, strict=True):
        probs = shape_probabilities(raw_probs, shape)
        nll -= log2(max(probs[token_id], 1e-300))
        entropy += entropy_bits(probs)
        top_probability += max(probs)

    return QualityMetrics(
        token_count=trace.token_count,
        avg_nll_bits=nll / trace.token_count,
        avg_entropy_bits=entropy / trace.token_count,
        avg_top_probability=top_probability / trace.token_count,
        greedy_preview=greedy_text,
    )


def greedy_preview(
    model: FixedLM | NGramLM | TransformerLM,
    *,
    settings: CodecSettings | None = None,
    max_chars: int = 80,
) -> str:
    settings = settings or CodecSettings()
    state = model.init_state()
    chars: list[str] = []
    for _ in range(max_chars):
        probs = shape_probabilities(model.step_probs(state), settings.shape)
        token_id = max(range(len(probs)), key=lambda idx: (probs[idx], -idx))
        chars.append(model.id_to_token(token_id))
        model.advance(state, token_id)
    return "".join(chars)


def _carrier_char_count(message: str) -> int:
    return len(_carrier_text(message))


def _carrier_text(message: str) -> str:
    lines = message.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    try:
        blank = lines.index("")
    except ValueError:
        return ""
    end = next((idx for idx, line in enumerate(lines) if line.strip() == "-----END LMCODEC-----"), len(lines))
    return "".join(lines[blank + 1 : end])
