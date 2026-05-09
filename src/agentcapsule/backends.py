"""Payload encoding backends for Agent Capsules."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from lmcodec.codec import decode as lmcodec_decode
from lmcodec.codec import encode as lmcodec_encode
from lmcodec.errors import LMCodecError
from lmcodec.lm import FixedLM, NGramLM

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


@dataclass(frozen=True)
class LMCodecFixedBackend:
    name: str = "lmcodec-fixed"

    def encode(self, payload: bytes, *, headers: Mapping[str, str] | None = None) -> str:
        return lmcodec_encode(payload, model=FixedLM(), wrap=80)

    def decode(self, text: str, *, headers: Mapping[str, str] | None = None) -> bytes:
        try:
            return lmcodec_decode(text, model=FixedLM())
        except LMCodecError as exc:
            raise CapsuleError(str(exc)) from exc


@dataclass(frozen=True)
class LMCodecNGramV2Backend:
    name: str = "lmcodec-ngram-v2"

    def encode(self, payload: bytes, *, headers: Mapping[str, str] | None = None) -> str:
        model = _ngram_model_from_headers(headers)
        try:
            return lmcodec_encode(payload, model=model, wrap=80)
        except LMCodecError as exc:
            raise CapsuleError(str(exc)) from exc

    def decode(self, text: str, *, headers: Mapping[str, str] | None = None) -> bytes:
        model = _ngram_model_from_headers(headers)
        try:
            return lmcodec_decode(text, model=model)
        except LMCodecError as exc:
            raise CapsuleError(str(exc)) from exc


_BACKENDS: dict[str, Backend] = {
    "base64": Base64Backend(),
    "lmcodec-fixed": LMCodecFixedBackend(),
    "lmcodec-ngram-v2": LMCodecNGramV2Backend(),
}


def get_backend(name: str) -> Backend:
    try:
        return _BACKENDS[name]
    except KeyError as exc:
        raise CapsuleError(f"unknown capsule codec: {name}") from exc


def known_codecs() -> tuple[str, ...]:
    return registry_known_codecs()


def ngram_v2_headers_from_model_path(path: str | Path) -> dict[str, str]:
    try:
        model = NGramLM.load(path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        raise CapsuleError(f"invalid n-gram model: {path}") from exc
    canonical = model.to_canonical_json()
    model_bytes = canonical.encode("utf-8")
    return {
        "lmcodec_backend_version": "ngram-v2",
        "lmcodec_model_type": model.model_type,
        "lmcodec_model_fingerprint": model.fingerprint,
        "lmcodec_model_sha256": hashlib.sha256(model_bytes).hexdigest(),
        "lmcodec_model_encoding": "inline-base64-json",
        "lmcodec_model_json_b64": base64.b64encode(model_bytes).decode("ascii"),
        "lmcodec_ngram_order": str(model.order),
        "lmcodec_ngram_uniform_mix": f"{model.uniform_mix:.17g}",
    }


def _ngram_model_from_headers(headers: Mapping[str, str] | None) -> NGramLM:
    if headers is None:
        raise CapsuleError("lmcodec-ngram-v2 requires inline model metadata")
    if headers.get("lmcodec_model_encoding") != "inline-base64-json":
        raise CapsuleError("lmcodec-ngram-v2 requires inline base64 model metadata")
    encoded = headers.get("lmcodec_model_json_b64")
    expected_sha = headers.get("lmcodec_model_sha256")
    expected_fingerprint = headers.get("lmcodec_model_fingerprint")
    if not encoded or not expected_sha or not expected_fingerprint:
        raise CapsuleError("lmcodec-ngram-v2 model metadata is incomplete")
    try:
        model_bytes = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (binascii.Error, UnicodeEncodeError) as exc:
        raise CapsuleError("invalid inline n-gram model encoding") from exc
    if hashlib.sha256(model_bytes).hexdigest() != expected_sha:
        raise CapsuleError("inline n-gram model SHA256 mismatch")
    model = _ngram_model_from_json(model_bytes)
    if model.fingerprint != expected_fingerprint:
        raise CapsuleError("inline n-gram model fingerprint mismatch")
    return model


def _ngram_model_from_json(model_bytes: bytes) -> NGramLM:
    try:
        data = json.loads(model_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CapsuleError("invalid inline n-gram model JSON") from exc
    if data.get("model_type") != NGramLM.model_type:
        raise CapsuleError("inline model is not an n-gram model")
    try:
        counts = {key: list(value) for key, value in data["counts"].items()}
        return NGramLM(
            vocab=data["vocab"],
            order=int(data["order"]),
            alpha=float(data["alpha"]),
            uniform_mix=float(data["uniform_mix"]),
            counts=counts,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise CapsuleError("invalid inline n-gram model fields") from exc
