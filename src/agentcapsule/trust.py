"""Local trust registry for Agent Capsule signatures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agentcapsule.errors import CapsulePolicyError
from agentcapsule.signing import decode_key_bytes, encode_key_bytes, load_public_key_file, public_key_fingerprint


@dataclass(frozen=True)
class TrustedKey:
    key_id: str
    fingerprint: str
    public_key: bytes | None = None
    status: str = "trusted"
    publisher: str | None = None
    organization: str | None = None
    domain: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    note: str | None = None

    @property
    def revoked(self) -> bool:
        return self.status == "revoked" or self.revoked_at is not None


@dataclass(frozen=True)
class SignatureTrustResult:
    status: str
    reason: str
    key_id: str | None = None
    fingerprint: str | None = None
    publisher: str | None = None
    organization: str | None = None
    domain: str | None = None
    public_key: bytes | None = None

    @property
    def trusted(self) -> bool:
        return self.status == "trusted"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "key_id": self.key_id,
            "fingerprint": self.fingerprint,
            "publisher": self.publisher,
            "organization": self.organization,
            "domain": self.domain,
        }


@dataclass(frozen=True)
class SignatureRegistry:
    keys: tuple[TrustedKey, ...]

    def resolve(
        self,
        *,
        key_id: str | None,
        fingerprint: str | None,
        now_iso: str | None = None,
    ) -> SignatureTrustResult:
        if not key_id and not fingerprint:
            return SignatureTrustResult("untrusted", "missing key id and fingerprint", key_id, fingerprint)

        matches = [
            key
            for key in self.keys
            if (not key_id or key.key_id == key_id) and (not fingerprint or key.fingerprint == fingerprint.lower())
        ]
        if not matches:
            return SignatureTrustResult("untrusted", "key not found in local registry", key_id, fingerprint)
        key = matches[0]
        if key.revoked:
            return SignatureTrustResult(
                "revoked",
                "key is revoked in local registry",
                key.key_id,
                key.fingerprint,
                key.publisher,
                key.organization,
                key.domain,
                key.public_key,
            )
        if key.expires_at and now_iso and now_iso > key.expires_at:
            return SignatureTrustResult(
                "expired",
                f"key expired at {key.expires_at}",
                key.key_id,
                key.fingerprint,
                key.publisher,
                key.organization,
                key.domain,
                key.public_key,
            )
        return SignatureTrustResult(
            "trusted",
            "key trusted by local registry",
            key.key_id,
            key.fingerprint,
            key.publisher,
            key.organization,
            key.domain,
            key.public_key,
        )


def load_signature_registry(path: Path) -> SignatureRegistry:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CapsulePolicyError(f"invalid signature registry JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CapsulePolicyError("signature registry JSON must be an object")
    keys = data.get("keys")
    if not isinstance(keys, list):
        raise CapsulePolicyError("signature registry must contain a keys list")
    return SignatureRegistry(tuple(_trusted_key_from_mapping(item, path.parent) for item in keys))


def registry_entry_from_public_key_file(
    *,
    key_id: str,
    public_key_path: Path,
    publisher: str | None = None,
    status: str = "trusted",
    note: str | None = None,
) -> dict[str, object]:
    public_key = load_public_key_file(public_key_path)
    entry: dict[str, object] = {
        "key_id": key_id,
        "fingerprint": public_key_fingerprint(public_key),
        "public_key": encode_key_bytes(public_key),
        "status": status,
    }
    if publisher:
        entry["publisher"] = publisher
    if note:
        entry["note"] = note
    return entry


def _trusted_key_from_mapping(data: Any, base_dir: Path) -> TrustedKey:
    if not isinstance(data, dict):
        raise CapsulePolicyError("signature registry key entries must be objects")
    key_id = _required_str(data, "key_id")
    fingerprint = _required_str(data, "fingerprint").lower()
    if len(fingerprint) != 64:
        raise CapsulePolicyError("signature registry fingerprint must be a SHA256 hex string")
    try:
        int(fingerprint, 16)
    except ValueError as exc:
        raise CapsulePolicyError("signature registry fingerprint must be a SHA256 hex string") from exc
    status = str(data.get("status", "trusted"))
    if status not in {"trusted", "revoked"}:
        raise CapsulePolicyError("signature registry key status must be trusted or revoked")
    public_key = _optional_public_key(data, base_dir)
    if public_key is not None and public_key_fingerprint(public_key) != fingerprint:
        raise CapsulePolicyError("signature registry public key does not match fingerprint")
    publisher = data.get("publisher")
    if publisher is not None and not isinstance(publisher, str):
        raise CapsulePolicyError("signature registry publisher must be a string")
    organization = data.get("organization")
    if organization is not None and not isinstance(organization, str):
        raise CapsulePolicyError("signature registry organization must be a string")
    domain = data.get("domain")
    if domain is not None and not isinstance(domain, str):
        raise CapsulePolicyError("signature registry domain must be a string")
    expires_at = data.get("expires_at")
    if expires_at is not None and not isinstance(expires_at, str):
        raise CapsulePolicyError("signature registry expires_at must be a string")
    revoked_at = data.get("revoked_at")
    if revoked_at is not None and not isinstance(revoked_at, str):
        raise CapsulePolicyError("signature registry revoked_at must be a string")
    note = data.get("note")
    if note is not None and not isinstance(note, str):
        raise CapsulePolicyError("signature registry note must be a string")
    return TrustedKey(
        key_id=key_id,
        fingerprint=fingerprint,
        public_key=public_key,
        status=status,
        publisher=publisher,
        organization=organization,
        domain=domain,
        expires_at=expires_at,
        revoked_at=revoked_at,
        note=note,
    )


def _required_str(data: dict[str, Any], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise CapsulePolicyError(f"signature registry key requires string field: {key}")
    return value


def _optional_public_key(data: dict[str, Any], base_dir: Path) -> bytes | None:
    public_key = data.get("public_key")
    public_key_path = data.get("public_key_path")
    if public_key and public_key_path:
        raise CapsulePolicyError("signature registry key cannot contain both public_key and public_key_path")
    if isinstance(public_key, str):
        return decode_key_bytes(public_key, expected_len=32, label="Ed25519 public key")
    if public_key is not None:
        raise CapsulePolicyError("signature registry public_key must be a string")
    if isinstance(public_key_path, str):
        return load_public_key_file(base_dir / public_key_path)
    if public_key_path is not None:
        raise CapsulePolicyError("signature registry public_key_path must be a string")
    return None
