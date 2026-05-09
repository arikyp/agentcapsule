"""High-level LMCodec orchestration."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from lmcodec.armour import make_armour, parse_armour
from lmcodec.bitstream import bits_to_bytes, bytes_to_bits
from lmcodec.errors import LMCodecError
from lmcodec.framing import HEADER_SIZE, build_frame, read_frame_header, try_parse_frame_bits
from lmcodec.lm import FixedLM, NGramLM
from lmcodec.probability import ProbabilityShapeSettings, shape_probabilities
from lmcodec.quantizer import DEFAULT_TOTAL, quantize
from lmcodec.range_coder import RangeDecoder, RangeEncoder
from lmcodec.transformer import TransformerLM


@dataclass(frozen=True)
class CodecSettings:
    total: int = DEFAULT_TOTAL
    topk: int = 0
    shape: ProbabilityShapeSettings = ProbabilityShapeSettings()

    def as_header(self) -> dict[str, str]:
        return {"TOT": str(self.total), "TOPK": str(self.topk), **self.shape.as_header()}

    @classmethod
    def from_header(cls, values: dict[str, str]) -> CodecSettings:
        try:
            total = int(values["TOT"])
            topk = int(values["TOPK"])
        except (KeyError, ValueError) as exc:
            raise LMCodecError("invalid settings") from exc
        return cls(
            total=total,
            topk=topk,
            shape=ProbabilityShapeSettings.from_header(values),
        )


def encode(
    payload: bytes,
    *,
    model: FixedLM | NGramLM | TransformerLM | None = None,
    settings: CodecSettings | None = None,
    wrap: int = 0,
    max_steps: int | None = None,
) -> str:
    """Encode bytes to armoured carrier text."""

    model = model or FixedLM()
    settings = settings or CodecSettings()
    _validate_settings(settings)

    target_bits = bytes_to_bits(build_frame(payload))
    source = RangeDecoder(target_bits, eof_pad_bit=0)
    mirror = RangeEncoder()
    state = model.init_state()
    tokens: list[str] = []
    cdf_cache: dict[tuple[float, ...], tuple[int, ...]] = {}

    step_limit = max_steps if max_steps is not None else max(1024, len(target_bits) * 64)
    steps = 0

    while not mirror.preview_finish_extends_prefix(target_bits):
        if steps >= step_limit:
            raise LMCodecError("encoding did not converge")
        cdf = _cached_cdf(model.step_probs(state), settings, cdf_cache)
        token_id = source.pop_symbol(cdf, validate=False)
        tokens.append(model.id_to_token(token_id))
        previous_bit_count = mirror.bit_count
        mirror.push_symbol(cdf, token_id, validate=False)
        if not mirror.emitted_prefix_matches_from(target_bits, previous_bit_count):
            raise AssertionError("range coder mirror diverged from target bits")
        model.advance(state, token_id)
        steps += 1

    return make_armour(
        "".join(tokens),
        model_fingerprint=model.fingerprint,
        settings=settings.as_header(),
        wrap=wrap,
    )


def decode(
    armoured_text: str,
    *,
    model: FixedLM | NGramLM | TransformerLM | None = None,
    settings: CodecSettings | None = None,
) -> bytes:
    """Decode armoured carrier text back to bytes."""

    model = model or FixedLM()
    block = parse_armour(armoured_text)
    if block.model_fingerprint != model.fingerprint:
        raise LMCodecError("fingerprint mismatch")
    actual_settings = CodecSettings.from_header(block.settings)
    _validate_settings(actual_settings)
    if settings is not None:
        _validate_settings(settings)
        _validate_armour_settings(actual_settings, settings)
    active_settings = actual_settings

    state = model.init_state()
    encoder = RangeEncoder()
    header_bits = HEADER_SIZE * 8
    frame_bits: int | None = None
    cdf_cache: dict[tuple[float, ...], tuple[int, ...]] = {}
    for token in block.payload_text:
        try:
            token_id = model.token_to_id(token)
        except ValueError as exc:
            raise LMCodecError(str(exc)) from exc
        cdf = _cached_cdf(model.step_probs(state), active_settings, cdf_cache)
        encoder.push_symbol(cdf, token_id, validate=False)
        model.advance(state, token_id)
        if frame_bits is None:
            if encoder.bit_count < header_bits:
                continue
            header = bits_to_bytes(encoder.bits_prefix(header_bits))
            frame_bits = read_frame_header(header).total_len * 8
        if encoder.bit_count >= frame_bits:
            payload = try_parse_frame_bits(encoder.bits_prefix(frame_bits))
            if payload is not None:
                return payload

    payload = try_parse_frame_bits(encoder.finish())
    if payload is not None:
        return payload

    raise LMCodecError("truncated message")


def _cached_cdf(
    raw_probs: Sequence[float],
    settings: CodecSettings,
    cache: dict[tuple[float, ...], tuple[int, ...]],
) -> tuple[int, ...]:
    key = tuple(raw_probs)
    cdf = cache.get(key)
    if cdf is None:
        probs = shape_probabilities(key, settings.shape)
        cdf = quantize(probs, total=settings.total).cdf
        cache[key] = cdf
    return cdf


def _validate_settings(settings: CodecSettings) -> None:
    if settings.total != DEFAULT_TOTAL:
        raise LMCodecError("invalid settings")
    if settings.topk != 0:
        raise LMCodecError("invalid settings")


def _validate_armour_settings(actual: CodecSettings, expected: CodecSettings) -> None:
    if actual != expected:
        raise LMCodecError("invalid settings")
