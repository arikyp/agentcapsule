"""Agent Capsule signing helpers."""

from __future__ import annotations

import base64
import hmac
import hashlib
import os
from dataclasses import replace
from pathlib import Path

from agentcapsule.envelope import CapsuleEnvelope
from agentcapsule.errors import CapsuleVerificationError

SIGNATURE_NONE = "none"
SIGNATURE_HMAC_SHA256 = "hmac-sha256"
SIGNATURE_ED25519 = "ed25519"
SIGNATURE_VALUE_HEADER = "signature_value"
SIGNATURE_VALUE_ENCODING_HEADER = "signature_value_encoding"
SIGNATURE_PUBLIC_KEY_HEADER = "signature_public_key"
SIGNATURE_PUBLIC_KEY_ENCODING_HEADER = "signature_public_key_encoding"
SIGNATURE_PUBLIC_KEY_FINGERPRINT_HEADER = "signature_public_key_fingerprint"
SIGNATURE_ENCODING_BASE64 = "base64"


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


def sign_envelope_ed25519(
    envelope: CapsuleEnvelope,
    *,
    private_key_bytes: bytes,
    key_id: str | None = None,
    inline_public_key: bool = True,
) -> CapsuleEnvelope:
    ed25519, serialization, _ = _cryptography_ed25519()
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key_bytes)
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    headers = dict(envelope.headers)
    headers["signature"] = SIGNATURE_ED25519
    if key_id:
        headers["signature_key_id"] = key_id
    headers[SIGNATURE_PUBLIC_KEY_FINGERPRINT_HEADER] = public_key_fingerprint(public_key_bytes)
    if inline_public_key:
        headers[SIGNATURE_PUBLIC_KEY_ENCODING_HEADER] = SIGNATURE_ENCODING_BASE64
        headers[SIGNATURE_PUBLIC_KEY_HEADER] = encode_key_bytes(public_key_bytes)
    else:
        headers.pop(SIGNATURE_PUBLIC_KEY_ENCODING_HEADER, None)
        headers.pop(SIGNATURE_PUBLIC_KEY_HEADER, None)
    headers[SIGNATURE_VALUE_ENCODING_HEADER] = SIGNATURE_ENCODING_BASE64
    headers.pop(SIGNATURE_VALUE_HEADER, None)
    signed = replace(envelope, headers=headers)
    headers[SIGNATURE_VALUE_HEADER] = encode_key_bytes(private_key.sign(signed_bytes(signed)))
    return replace(envelope, headers=headers)


def verify_ed25519_signature(envelope: CapsuleEnvelope, *, public_key_bytes: bytes | None = None) -> None:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    if mode == SIGNATURE_NONE:
        return
    if mode != SIGNATURE_ED25519:
        raise CapsuleVerificationError(f"unsupported signature mode: {mode}")
    _, _, invalid_signature = _cryptography_ed25519()
    if public_key_bytes is None:
        public_key_bytes = inline_public_key_bytes(envelope)
    _check_public_key_fingerprint(envelope, public_key_bytes)
    signature = _signature_value_bytes(envelope)
    public_key = _ed25519_public_key(public_key_bytes)
    try:
        public_key.verify(signature, signed_bytes(envelope))
    except invalid_signature as exc:
        raise CapsuleVerificationError("signature verification failed") from exc


def generate_ed25519_keypair() -> tuple[bytes, bytes]:
    ed25519, serialization, _ = _cryptography_ed25519()
    private_key = ed25519.Ed25519PrivateKey.generate()
    private_key_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return private_key_bytes, public_key_bytes


def load_private_key_file(path: Path) -> bytes:
    return _load_base64_key_file(path, expected_len=32, label="Ed25519 private key")


def load_public_key_file(path: Path) -> bytes:
    return _load_base64_key_file(path, expected_len=32, label="Ed25519 public key")


def write_key_file(path: Path, key_bytes: bytes) -> None:
    path.write_text(encode_key_bytes(key_bytes) + "\n", encoding="utf-8", newline="\n")


def encode_key_bytes(key_bytes: bytes) -> str:
    return base64.b64encode(key_bytes).decode("ascii")


def decode_key_bytes(value: str, *, expected_len: int, label: str) -> bytes:
    return _decode_base64_bytes(value, expected_len=expected_len, label=label)


def inline_public_key_bytes(envelope: CapsuleEnvelope) -> bytes:
    encoding = envelope.headers.get(SIGNATURE_PUBLIC_KEY_ENCODING_HEADER)
    if encoding != SIGNATURE_ENCODING_BASE64:
        raise CapsuleVerificationError("missing inline Ed25519 public key")
    value = envelope.headers.get(SIGNATURE_PUBLIC_KEY_HEADER)
    if not value:
        raise CapsuleVerificationError("missing inline Ed25519 public key")
    return decode_key_bytes(value, expected_len=32, label="Ed25519 public key")


def public_key_fingerprint(public_key_bytes: bytes) -> str:
    return hashlib.sha256(public_key_bytes).hexdigest()


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


def _signature_value_bytes(envelope: CapsuleEnvelope) -> bytes:
    if envelope.headers.get(SIGNATURE_VALUE_ENCODING_HEADER) != SIGNATURE_ENCODING_BASE64:
        raise CapsuleVerificationError("missing Ed25519 signature value encoding")
    value = envelope.headers.get(SIGNATURE_VALUE_HEADER)
    if not value:
        raise CapsuleVerificationError("missing signature value")
    return _decode_base64_bytes(value, expected_len=64, label="Ed25519 signature")


def _check_public_key_fingerprint(envelope: CapsuleEnvelope, public_key_bytes: bytes) -> None:
    expected = envelope.headers.get(SIGNATURE_PUBLIC_KEY_FINGERPRINT_HEADER)
    if not expected:
        raise CapsuleVerificationError("missing Ed25519 public key fingerprint")
    actual = public_key_fingerprint(public_key_bytes)
    if not hmac.compare_digest(actual, expected.lower()):
        raise CapsuleVerificationError("public key fingerprint mismatch")


def _ed25519_public_key(public_key_bytes: bytes):
    ed25519, _, _ = _cryptography_ed25519()
    return ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)


def _load_base64_key_file(path: Path, *, expected_len: int, label: str) -> bytes:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CapsuleVerificationError(f"failed to read {label}: {path}") from exc
    return _decode_base64_bytes(text, expected_len=expected_len, label=label)


def _decode_base64_bytes(value: str, *, expected_len: int, label: str) -> bytes:
    try:
        data = base64.b64decode(value.encode("ascii"), validate=True)
    except Exception as exc:
        raise CapsuleVerificationError(f"invalid {label}") from exc
    if len(data) != expected_len:
        raise CapsuleVerificationError(f"invalid {label} length")
    return data


def _cryptography_ed25519():
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise CapsuleVerificationError("Ed25519 support requires installing lmcodec[signing]") from exc
    return ed25519, serialization, InvalidSignature
