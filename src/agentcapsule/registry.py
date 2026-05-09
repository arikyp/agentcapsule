"""Static codec registry for Agent Capsule V0."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CodecDescriptor:
    name: str
    purpose: str
    stability: str
    requires_external_model: bool
    notes: str


_CODECS: tuple[CodecDescriptor, ...] = (
    CodecDescriptor(
        name="base64",
        purpose="stable interoperability baseline",
        stability="stable-v0",
        requires_external_model=False,
        notes="standard-library base64 for tests and broad tool compatibility",
    ),
    CodecDescriptor(
        name="lmcodec-fixed",
        purpose="LMCodec fixed carrier backend",
        stability="experimental-v0",
        requires_external_model=False,
        notes="uses the existing default FixedLM path; no V2 registry required",
    ),
)


def list_codecs() -> tuple[CodecDescriptor, ...]:
    return _CODECS


def known_codecs() -> tuple[str, ...]:
    return tuple(codec.name for codec in _CODECS)


def describe_codec(name: str) -> CodecDescriptor | None:
    for codec in _CODECS:
        if codec.name == name:
            return codec
    return None
