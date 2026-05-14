"""Agent Capsule encryption helpers."""

from __future__ import annotations

import base64
import json
import os
from typing import TYPE_CHECKING

from agentcapsule.errors import CapsuleVerificationError

if TYPE_CHECKING:
    from agentcapsule.envelope import CapsuleEnvelope

ENCRYPTION_NONE = "none"
ENCRYPTION_AES_256_GCM = "aes-256-gcm"

ENCRYPTION_KEY_ID_HEADER = "encryption_key_id"
ENCRYPTION_NONCE_HEADER = "encryption_nonce"
ENCRYPTION_TAG_HEADER = "encryption_tag"
ENCRYPTION_ENCODING_BASE64 = "base64"


def encrypt_payload(
    payload: bytes,
    *,
    key: bytes,
    mode: str = ENCRYPTION_AES_256_GCM,
    associated_data: bytes | None = None,
) -> tuple[bytes, dict[str, str]]:
    if mode != ENCRYPTION_AES_256_GCM:
        raise CapsuleVerificationError(f"unsupported encryption mode: {mode}")

    if len(key) != 32:
        raise CapsuleVerificationError("AES-256-GCM requires a 32-byte key")

    aesgcm = _cryptography_aesgcm()
    nonce = os.urandom(12)
    # Bind ciphertext authenticity to selected envelope headers.
    ciphertext_with_tag = aesgcm(key).encrypt(nonce, payload, associated_data)
    
    # AESGCM.encrypt returns ciphertext + tag (16 bytes)
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]

    headers = {
        "encryption": mode,
        ENCRYPTION_NONCE_HEADER: base64.b64encode(nonce).decode("ascii"),
        ENCRYPTION_TAG_HEADER: base64.b64encode(tag).decode("ascii"),
    }
    return ciphertext, headers


def decrypt_payload(envelope: CapsuleEnvelope, *, key: bytes) -> bytes:
    mode = envelope.headers.get("encryption", ENCRYPTION_NONE)
    if mode == ENCRYPTION_NONE:
        return envelope.decode_payload()

    if mode != ENCRYPTION_AES_256_GCM:
        raise CapsuleVerificationError(f"unsupported encryption mode: {mode}")

    if len(key) != 32:
        raise CapsuleVerificationError("AES-256-GCM requires a 32-byte key")

    nonce_b64 = envelope.headers.get(ENCRYPTION_NONCE_HEADER)
    tag_b64 = envelope.headers.get(ENCRYPTION_TAG_HEADER)

    if not nonce_b64 or not tag_b64:
        raise CapsuleVerificationError("missing encryption nonce or tag")

    try:
        nonce = base64.b64decode(nonce_b64.encode("ascii"), validate=True)
        tag = base64.b64decode(tag_b64.encode("ascii"), validate=True)
    except Exception as exc:
        raise CapsuleVerificationError("invalid encryption nonce or tag encoding") from exc

    if len(nonce) != 12:
        raise CapsuleVerificationError("invalid encryption nonce length")
    if len(tag) != 16:
        raise CapsuleVerificationError("invalid encryption tag length")

    ciphertext = envelope.decode_payload()
    associated_data = associated_data_for_headers(envelope.headers)
    aesgcm = _cryptography_aesgcm()
    
    try:
        return aesgcm(key).decrypt(nonce, ciphertext + tag, associated_data)
    except Exception as exc:
        raise CapsuleVerificationError("decryption failed (invalid key or tampered data)") from exc


def associated_data_for_headers(headers: dict[str, str]) -> bytes:
    """Return canonical associated data for AES-GCM header binding."""
    excluded = {
        ENCRYPTION_NONCE_HEADER,
        ENCRYPTION_TAG_HEADER,
        "signature",
        "signature_key_id",
        "signature_public_key_fingerprint",
        "signature_public_key_encoding",
        "signature_public_key",
        "signature_value_encoding",
        "signature_value",
    }
    aad_headers = {key: value for key, value in headers.items() if key not in excluded}
    canonical = json.dumps(aad_headers, sort_keys=True, separators=(",", ":"))
    return canonical.encode("utf-8")


def _cryptography_aesgcm():
    try:
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    except ImportError as exc:
        raise CapsuleVerificationError("encryption support requires installing lmcodec[signing]") from exc
    return AESGCM
