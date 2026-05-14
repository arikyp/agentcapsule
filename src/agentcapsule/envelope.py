"""Agent Capsule V0 envelope parsing and rendering."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime

from agentcapsule.backends import get_backend
from agentcapsule.errors import CapsuleParseError, CapsuleVerificationError
from agentcapsule.manifest import (
    CAPSULE_MANIFEST_HEADER,
    DEFAULT_CAPSULE_TYPE,
    build_capsule_manifest,
    encode_capsule_manifest,
    file_manifest_entry,
    parse_capsule_manifest,
)

BEGIN_MARKER = "-----BEGIN AGENT CAPSULE-----"
PAYLOAD_MARKER = "-----PAYLOAD-----"
END_MARKER = "-----END AGENT CAPSULE-----"

CAPSULE_VERSION = "0.1"

REQUIRED_HEADERS = (
    "capsule_version",
    "codec",
    "content_type",
    "payload_sha256",
    "compression",
    "encryption",
    "signature",
    "created_by",
    "created_at",
    "policy",
)

HEADER_ORDER = (
    "capsule_version",
    "codec",
    "content_type",
    "capsule_manifest",
    "lmcodec_backend_version",
    "lmcodec_model_type",
    "lmcodec_model_fingerprint",
    "lmcodec_model_sha256",
    "lmcodec_model_encoding",
    "lmcodec_ngram_order",
    "lmcodec_ngram_uniform_mix",
    "payload_sha256",
    "compression",
    "encryption",
    "encryption_key_id",
    "encryption_nonce",
    "encryption_tag",
    "signature",
    "signature_key_id",
    "signature_public_key_fingerprint",
    "signature_public_key_encoding",
    "signature_public_key",
    "signature_value_encoding",
    "signature_value",
    "created_by",
    "created_at",
    "policy",
    "filename",
)


@dataclass(frozen=True)
class CapsuleEnvelope:
    headers: dict[str, str]
    payload_text: str

    @property
    def codec(self) -> str:
        return self.headers["codec"]

    @property
    def content_type(self) -> str:
        return self.headers["content_type"]

    @property
    def payload_sha256(self) -> str:
        return self.headers["payload_sha256"]

    @property
    def capsule_manifest(self) -> dict[str, object] | None:
        value = self.headers.get(CAPSULE_MANIFEST_HEADER)
        if value is None:
            return None
        return parse_capsule_manifest(value)

    def decode_payload(self) -> bytes:
        return get_backend(self.codec).decode(self.payload_text, headers=self.headers)


def utc_timestamp() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def build_envelope(
    payload: bytes,
    *,
    codec: str = "base64",
    content_type: str = "application/octet-stream",
    filename: str | None = None,
    created_by: str = "local",
    created_at: str | None = None,
    policy: str = "inspect-before-use",
    capsule_type: str = DEFAULT_CAPSULE_TYPE,
    task_id: str = "",
    manifest_files: list[dict[str, object]] | None = None,
    requested_capabilities: list[str] | None = None,
    policy_hints: dict[str, object] | None = None,
    delivery_mode: str = "inline",
    delivery_uri: str | None = None,
    compression: str = "none",
    encryption_key: bytes | None = None,
    encryption_key_id: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> CapsuleEnvelope:
    payload_sha256 = hashlib.sha256(payload).hexdigest()
    if manifest_files is None:
        manifest_files = [file_manifest_entry(filename or "payload.bin", payload)]
    
    headers = {
        "capsule_version": CAPSULE_VERSION,
        "codec": codec,
        "content_type": content_type,
        "capsule_manifest": encode_capsule_manifest(
            build_capsule_manifest(
                capsule_type=capsule_type,
                created_by=created_by,
                task_id=task_id,
                files=manifest_files,
                requested_capabilities=requested_capabilities,
                policy_hints=policy_hints,
                delivery_mode=delivery_mode,
                delivery_uri=delivery_uri,
            )
        ),
        "payload_sha256": payload_sha256,
        "compression": compression,
        "encryption": "none",
        "signature": "none",
        "created_by": created_by,
        "created_at": created_at or utc_timestamp(),
        "policy": policy,
    }
    if filename:
        headers["filename"] = filename

    if compression != "none":
        from agentcapsule.compression import compress_payload
        payload, _ = compress_payload(payload, mode=compression)

    if extra_headers:
        headers.update(extra_headers)

    if encryption_key:
        from agentcapsule.encryption import associated_data_for_headers, encrypt_payload
        headers["encryption"] = "aes-256-gcm"
        if encryption_key_id:
            headers["encryption_key_id"] = encryption_key_id
        payload, encryption_headers = encrypt_payload(
            payload,
            key=encryption_key,
            associated_data=associated_data_for_headers(headers),
        )
        headers.update(encryption_headers)
    if CAPSULE_MANIFEST_HEADER in headers:
        parse_capsule_manifest(headers[CAPSULE_MANIFEST_HEADER])
    payload_text = get_backend(codec).encode(payload, headers=headers)
    return CapsuleEnvelope(headers=headers, payload_text=payload_text)


def render_envelope(envelope: CapsuleEnvelope) -> str:
    lines = [BEGIN_MARKER]
    emitted = set()
    for key in HEADER_ORDER:
        if key in envelope.headers:
            lines.append(f"{key}: {envelope.headers[key]}")
            emitted.add(key)
    for key in sorted(set(envelope.headers) - emitted):
        lines.append(f"{key}: {envelope.headers[key]}")
    lines.append(PAYLOAD_MARKER)
    lines.extend(envelope.payload_text.split("\n"))
    lines.append(END_MARKER)
    return "\n".join(lines) + "\n"


def parse_envelope(text: str) -> CapsuleEnvelope:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    begin = normalized.find(BEGIN_MARKER)
    if begin < 0:
        raise CapsuleParseError("missing capsule begin marker")
    payload = normalized.find(PAYLOAD_MARKER, begin + len(BEGIN_MARKER))
    if payload < 0:
        raise CapsuleParseError("missing capsule payload marker")
    end = normalized.find(END_MARKER, payload + len(PAYLOAD_MARKER))
    if end < 0:
        raise CapsuleParseError("missing capsule end marker")
    extra_begin = normalized.find(BEGIN_MARKER, begin + len(BEGIN_MARKER), end)
    if extra_begin >= 0:
        raise CapsuleParseError("nested capsule begin marker")

    header_text = normalized[begin + len(BEGIN_MARKER) : payload]
    headers = _parse_headers(header_text)
    payload_text = normalized[payload + len(PAYLOAD_MARKER) : end]
    if payload_text.startswith("\n"):
        payload_text = payload_text[1:]
    if payload_text.endswith("\n"):
        payload_text = payload_text[:-1]
    return CapsuleEnvelope(headers=headers, payload_text=payload_text)


def verify_envelope(envelope: CapsuleEnvelope, *, encryption_key: bytes | None = None) -> bytes:
    if envelope.headers.get("encryption", "none") != "none":
        if encryption_key is None:
            raise CapsuleVerificationError("capsule is encrypted but no decryption key provided")
        from agentcapsule.encryption import decrypt_payload
        payload = decrypt_payload(envelope, key=encryption_key)
    else:
        payload = envelope.decode_payload()

    if envelope.headers.get("compression", "none") != "none":
        from agentcapsule.compression import decompress_payload
        payload = decompress_payload(payload, mode=envelope.headers["compression"])

    actual = hashlib.sha256(payload).hexdigest()
    expected = envelope.payload_sha256.lower()
    if actual != expected:
        raise CapsuleVerificationError("payload SHA256 mismatch")
    return payload


def parse_and_verify(text: str, *, encryption_key: bytes | None = None) -> tuple[CapsuleEnvelope, bytes]:
    envelope = parse_envelope(text)
    payload = verify_envelope(envelope, encryption_key=encryption_key)
    return envelope, payload


def _parse_headers(header_text: str) -> dict[str, str]:
    headers: dict[str, str] = {}
    for raw_line in header_text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        if line in (BEGIN_MARKER, PAYLOAD_MARKER, END_MARKER):
            raise CapsuleParseError("malformed capsule boundary")
        if ":" not in line:
            raise CapsuleParseError(f"malformed header line: {line}")
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise CapsuleParseError("empty capsule header key or value")
        if key in headers:
            raise CapsuleParseError(f"duplicate capsule header: {key}")
        headers[key] = value

    missing = [key for key in REQUIRED_HEADERS if key not in headers]
    if missing:
        raise CapsuleParseError(f"missing required capsule headers: {', '.join(missing)}")
    if headers["capsule_version"] != CAPSULE_VERSION:
        raise CapsuleParseError("unsupported capsule version")
    if len(headers["payload_sha256"]) != 64:
        raise CapsuleParseError("invalid payload SHA256")
    try:
        int(headers["payload_sha256"], 16)
    except ValueError as exc:
        raise CapsuleParseError("invalid payload SHA256") from exc
    if CAPSULE_MANIFEST_HEADER in headers:
        parse_capsule_manifest(headers[CAPSULE_MANIFEST_HEADER])
    return headers
