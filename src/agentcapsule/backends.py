"""Payload encoding backends for Agent Capsules."""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
from typing import Protocol

from lmcodec.codec import decode as lmcodec_decode
from lmcodec.codec import encode as lmcodec_encode
from lmcodec.errors import LMCodecError
from lmcodec.lm import FixedLM

from agentcapsule.errors import CapsuleError
from agentcapsule.registry import known_codecs as registry_known_codecs


class Backend(Protocol):
    name: str

    def encode(self, payload: bytes) -> str:
        """Encode bytes into text."""

    def decode(self, text: str) -> bytes:
        """Decode text into bytes."""


@dataclass(frozen=True)
class Base64Backend:
    name: str = "base64"

    def encode(self, payload: bytes) -> str:
        return base64.b64encode(payload).decode("ascii")

    def decode(self, text: str) -> bytes:
        compact = "".join(text.split())
        try:
            return base64.b64decode(compact.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise CapsuleError("invalid base64 payload") from exc


@dataclass(frozen=True)
class LMCodecFixedBackend:
    name: str = "lmcodec-fixed"

    def encode(self, payload: bytes) -> str:
        return lmcodec_encode(payload, model=FixedLM(), wrap=80)

    def decode(self, text: str) -> bytes:
        try:
            return lmcodec_decode(text, model=FixedLM())
        except LMCodecError as exc:
            raise CapsuleError(str(exc)) from exc


_BACKENDS: dict[str, Backend] = {
    "base64": Base64Backend(),
    "lmcodec-fixed": LMCodecFixedBackend(),
}


def get_backend(name: str) -> Backend:
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise CapsuleError(f"unknown capsule codec: {name}") from exc


def known_codecs() -> tuple[str, ...]:
    return registry_known_codecs()
