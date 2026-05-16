"""Local trust registry for Agent Capsule signatures."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

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
        now_dt = _parse_iso8601(now_iso, field_name="now_iso") if now_iso else datetime.now(UTC)
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
        if key.expires_at:
            expires_dt = _parse_iso8601(key.expires_at, field_name="expires_at")
            if now_dt > expires_dt:
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


@dataclass(frozen=True)
class VerifiedRegistrySnapshot:
    registry: SignatureRegistry
    registry_version: int
    issuer: str
    sequence: int
    created_at: str
    expires_at: str | None
    signature_key_id: str | None


def load_signature_registry(path: Path) -> SignatureRegistry:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CapsulePolicyError(f"invalid signature registry JSON: {exc}") from exc
    return signature_registry_from_mapping(data, base_dir=path.parent)


def load_signature_registries(paths: Sequence[Path]) -> SignatureRegistry:
    if not paths:
        raise CapsulePolicyError("at least one signature registry path is required")
    return merge_signature_registries(load_signature_registry(path) for path in paths)


def signature_registry_from_mapping(data: Any, *, base_dir: Path) -> SignatureRegistry:
    if not isinstance(data, dict):
        raise CapsulePolicyError("signature registry JSON must be an object")
    keys = data.get("keys")
    if not isinstance(keys, list):
        raise CapsulePolicyError("signature registry must contain a keys list")
    return SignatureRegistry(tuple(_trusted_key_from_mapping(item, base_dir) for item in keys))


def merge_signature_registries(registries: Iterable[SignatureRegistry]) -> SignatureRegistry:
    merged_by_identity: dict[tuple[str, str], TrustedKey] = {}
    for registry in registries:
        for key in registry.keys:
            identity = (key.key_id, key.fingerprint)
            existing = merged_by_identity.get(identity)
            if existing is None:
                merged_by_identity[identity] = key
                continue
            if existing.revoked:
                continue
            if key.revoked:
                merged_by_identity[identity] = key
                continue
    merged_keys = sorted(merged_by_identity.values(), key=lambda item: (item.key_id, item.fingerprint))
    return SignatureRegistry(tuple(merged_keys))


def verify_signed_registry_snapshot(
    data: Any,
    *,
    trusted_root_public_keys: Sequence[bytes],
    base_dir: Path,
    expected_issuer: str | None = None,
    now_iso: str | None = None,
) -> VerifiedRegistrySnapshot:
    if not isinstance(data, dict):
        raise CapsulePolicyError("registry snapshot JSON must be an object")
    registry_version = data.get("registry_version")
    if registry_version != 1:
        raise CapsulePolicyError("registry snapshot registry_version must be 1")
    issuer = data.get("issuer")
    if not isinstance(issuer, str) or not issuer:
        raise CapsulePolicyError("registry snapshot issuer must be a non-empty string")
    if expected_issuer and issuer != expected_issuer:
        raise CapsulePolicyError("registry snapshot issuer does not match expected issuer")
    sequence = data.get("sequence")
    if not isinstance(sequence, int) or sequence < 0:
        raise CapsulePolicyError("registry snapshot sequence must be a non-negative integer")
    created_at = data.get("created_at")
    if not isinstance(created_at, str):
        raise CapsulePolicyError("registry snapshot created_at must be a string")
    _parse_iso8601(created_at, field_name="created_at")
    expires_at = data.get("expires_at")
    if expires_at is not None and not isinstance(expires_at, str):
        raise CapsulePolicyError("registry snapshot expires_at must be a string")
    now_dt = _parse_iso8601(now_iso, field_name="now_iso") if now_iso else datetime.now(UTC)
    if expires_at:
        expires_dt = _parse_iso8601(expires_at, field_name="expires_at")
        if now_dt > expires_dt:
            raise CapsulePolicyError(f"registry snapshot expired at {expires_at}")
    signature = data.get("signature")
    if not isinstance(signature, dict):
        raise CapsulePolicyError("registry snapshot signature must be an object")
    mode = signature.get("mode")
    if mode != "ed25519":
        raise CapsulePolicyError("registry snapshot signature mode must be ed25519")
    key_id = signature.get("key_id")
    if key_id is not None and not isinstance(key_id, str):
        raise CapsulePolicyError("registry snapshot signature key_id must be a string")
    signature_value = signature.get("signature")
    if not isinstance(signature_value, str):
        raise CapsulePolicyError("registry snapshot signature value must be a string")
    if not trusted_root_public_keys:
        raise CapsulePolicyError("at least one trusted root public key is required")
    signature_bytes = decode_key_bytes(signature_value, expected_len=64, label="registry snapshot signature")
    signing_payload = _snapshot_signing_payload(data)
    _verify_ed25519_detached_signature(
        signing_payload,
        signature_bytes=signature_bytes,
        trusted_root_public_keys=trusted_root_public_keys,
    )
    registry = signature_registry_from_mapping(data, base_dir=base_dir)
    return VerifiedRegistrySnapshot(
        registry=registry,
        registry_version=registry_version,
        issuer=issuer,
        sequence=sequence,
        created_at=created_at,
        expires_at=expires_at,
        signature_key_id=key_id,
    )


def signature_registry_to_dict(registry: SignatureRegistry) -> dict[str, object]:
    return {"keys": [_trusted_key_to_mapping(item) for item in registry.keys]}


def verified_snapshot_to_registry_document(snapshot: VerifiedRegistrySnapshot) -> dict[str, object]:
    payload = signature_registry_to_dict(snapshot.registry)
    payload["source_snapshot"] = {
        "registry_version": snapshot.registry_version,
        "issuer": snapshot.issuer,
        "sequence": snapshot.sequence,
        "created_at": snapshot.created_at,
        "expires_at": snapshot.expires_at,
        "signature_key_id": snapshot.signature_key_id,
    }
    return payload


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
    if isinstance(expires_at, str):
        _parse_iso8601(expires_at, field_name="expires_at")
    revoked_at = data.get("revoked_at")
    if revoked_at is not None and not isinstance(revoked_at, str):
        raise CapsulePolicyError("signature registry revoked_at must be a string")
    if isinstance(revoked_at, str):
        _parse_iso8601(revoked_at, field_name="revoked_at")
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


def _parse_iso8601(value: str, *, field_name: str) -> datetime:
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise CapsulePolicyError(f"signature registry {field_name} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise CapsulePolicyError(f"signature registry {field_name} must include timezone information")
    return parsed.astimezone(UTC)


def _snapshot_signing_payload(data: dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in data.items() if key != "signature"}
    return json.dumps(unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def _verify_ed25519_detached_signature(
    payload: bytes,
    *,
    signature_bytes: bytes,
    trusted_root_public_keys: Sequence[bytes],
) -> None:
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric import ed25519
    except ImportError as exc:
        raise CapsulePolicyError("registry snapshot verification requires installing agentcapsule[signing]") from exc
    for public_key_bytes in trusted_root_public_keys:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
        try:
            public_key.verify(signature_bytes, payload)
            return
        except InvalidSignature:
            continue
    raise CapsulePolicyError("registry snapshot signature verification failed")


def _trusted_key_to_mapping(key: TrustedKey) -> dict[str, object]:
    payload: dict[str, object] = {
        "key_id": key.key_id,
        "fingerprint": key.fingerprint,
        "status": key.status,
    }
    if key.public_key is not None:
        payload["public_key"] = encode_key_bytes(key.public_key)
    if key.publisher is not None:
        payload["publisher"] = key.publisher
    if key.organization is not None:
        payload["organization"] = key.organization
    if key.domain is not None:
        payload["domain"] = key.domain
    if key.expires_at is not None:
        payload["expires_at"] = key.expires_at
    if key.revoked_at is not None:
        payload["revoked_at"] = key.revoked_at
    if key.note is not None:
        payload["note"] = key.note
    return payload
