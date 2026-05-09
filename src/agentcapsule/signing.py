"""Dependency-free Agent Capsule HMAC signing."""

from __future__ import annotations

import hmac
import hashlib
import os
from dataclasses import replace

from agentcapsule.envelope import CapsuleEnvelope
from agentcapsule.errors import CapsuleVerificationError

SIGNATURE_NONE = "none"
SIGNATURE_HMAC_SHA256 = "hmac-sha256"
SIGNATURE_VALUE_HEADER = "signature_value"


def sign_envelope(envelope: CapsuleEnvelope, *, key: bytes, key_id: str | None = None) -> CapsuleEnvelope:
    headers = dict(envelope.headers)
    headers["signature"] = SIGNATURE_HMAC_SHA256
    if key_id:
        headers["signature_key_id"] = key_id
    headers.pop(SIGNATURE_VALUE_HEADER, None)
    signed = replace(envelope, headers=headers)
    headers[SIGNATURE_VALUE_HEADER] = _hmac_hex(signed, key)
    return replace(envelope, headers=headers)


def verify_signature(envelope: CapsuleEnvelope, *, key: bytes) -> None:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    if mode == SIGNATURE_NONE:
        return
    if mode != SIGNATURE_HMAC_SHA256:
        raise CapsuleVerificationError(f"unsupported signature mode: {mode}")
    expected = envelope.headers.get(SIGNATURE_VALUE_HEADER)
    if not expected:
        raise CapsuleVerificationError("missing signature value")
    actual = _hmac_hex(envelope, key)
    if not hmac.compare_digest(actual, expected):
        raise CapsuleVerificationError("signature verification failed")


def key_from_env(env_name: str) -> bytes:
    value = os.environ.get(env_name)
    if value is None:
        raise CapsuleVerificationError(f"missing signature key environment variable: {env_name}")
    return value.encode("utf-8")


def signed_bytes(envelope: CapsuleEnvelope) -> bytes:
    lines = ["AGENT-CAPSULE-SIGNATURE-V0"]
    for key in sorted(envelope.headers):
        if key == SIGNATURE_VALUE_HEADER:
            continue
        lines.append(f"{key}: {envelope.headers[key]}")
    lines.append("")
    lines.append(envelope.payload_text)
    return "\n".join(lines).encode("utf-8")


def _hmac_hex(envelope: CapsuleEnvelope, key: bytes) -> str:
    return hmac.new(key, signed_bytes(envelope), hashlib.sha256).hexdigest()
