"""Payload encoding backends for Agent Capsules."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from agentcapsule.errors import CapsuleError
from agentcapsule.registry import known_codecs as registry_known_codecs


class Backend(Protocol):
    name: str

    def encode(self, payload: bytes, *, headers: Mapping[str, str] | None = None) -> str:
        """Encode bytes into text."""

    def decode(self, text: str, *, headers: Mapping[str, str] | None = None) -> bytes:
        """Decode text into bytes."""


@dataclass(frozen=True)
class Base64Backend:
    name: str = "base64"

    def encode(self, payload: bytes, *, headers: Mapping[str, str] | None = None) -> str:
        return base64.b64encode(payload).decode("ascii")

    def decode(self, text: str, *, headers: Mapping[str, str] | None = None) -> bytes:
        compact = "".join(text.split())
        try:
            return base64.b64decode(compact.encode("ascii"), validate=True)
        except (binascii.Error, UnicodeEncodeError) as exc:
            raise CapsuleError("invalid base64 payload") from exc


_BACKENDS: dict[str, Backend] = {
    "base64": Base64Backend(),
}


def get_backend(name: str) -> Backend:
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise CapsuleError(f"unknown capsule codec: {name}") from exc


def known_codecs() -> tuple[str, ...]:
    return registry_known_codecs()
