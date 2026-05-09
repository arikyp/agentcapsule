"""Minimal Agent Capsule policy defaults."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agentcapsule.backends import known_codecs
from agentcapsule.envelope import CapsuleEnvelope
from agentcapsule.errors import CapsulePolicyError
from agentcapsule.manifest import BUNDLE_CONTENT_TYPE, SINGLE_FILE_CONTENT_TYPE


@dataclass(frozen=True)
class CapsulePolicy:
    require_known_codec: bool = True
    require_hash: bool = True
    allow_unsigned: bool = True
    required_signature_modes: frozenset[str] = field(default_factory=frozenset)
    allowed_content_types: frozenset[str] = field(
        default_factory=lambda: frozenset({SINGLE_FILE_CONTENT_TYPE, BUNDLE_CONTENT_TYPE})
    )
    max_payload_bytes: int = 16 * 1024 * 1024
    decode_to_sandbox_required: bool = True

    def check_metadata(self, envelope: CapsuleEnvelope) -> None:
        if self.require_known_codec and envelope.codec not in known_codecs():
            raise CapsulePolicyError(f"unknown codec is not allowed: {envelope.codec}")
        if self.require_hash and not envelope.headers.get("payload_sha256"):
            raise CapsulePolicyError("payload hash is required")
        if not self.allow_unsigned and envelope.headers.get("signature") == "none":
            raise CapsulePolicyError("unsigned capsules are not allowed")
        if self.required_signature_modes and envelope.headers.get("signature") not in self.required_signature_modes:
            raise CapsulePolicyError("signature mode is not allowed")
        if envelope.content_type not in self.allowed_content_types:
            raise CapsulePolicyError(f"content type is not allowed: {envelope.content_type}")

    def check_payload(self, payload: bytes) -> None:
        if len(payload) > self.max_payload_bytes:
            raise CapsulePolicyError("payload exceeds maximum allowed size")


DEFAULT_POLICY = CapsulePolicy()

_POLICY_FIELDS = {
    "require_known_codec",
    "require_hash",
    "allow_unsigned",
    "required_signature_modes",
    "allowed_content_types",
    "max_payload_bytes",
    "decode_to_sandbox_required",
}


def load_policy(path: Path) -> CapsulePolicy:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CapsulePolicyError(f"invalid policy JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise CapsulePolicyError("policy JSON must be an object")
    return policy_from_mapping(data)


def policy_to_dict(policy: CapsulePolicy) -> dict[str, object]:
    return {
        "require_known_codec": policy.require_known_codec,
        "require_hash": policy.require_hash,
        "allow_unsigned": policy.allow_unsigned,
        "required_signature_modes": sorted(policy.required_signature_modes),
        "allowed_content_types": sorted(policy.allowed_content_types),
        "max_payload_bytes": policy.max_payload_bytes,
        "decode_to_sandbox_required": policy.decode_to_sandbox_required,
    }


def policy_from_mapping(data: dict[str, Any]) -> CapsulePolicy:
    unknown = sorted(set(data) - _POLICY_FIELDS)
    if unknown:
        raise CapsulePolicyError(f"unknown policy fields: {', '.join(unknown)}")

    values: dict[str, Any] = {}
    for key in (
        "require_known_codec",
        "require_hash",
        "allow_unsigned",
        "decode_to_sandbox_required",
    ):
        if key in data:
            value = data[key]
            if not isinstance(value, bool):
                raise CapsulePolicyError(f"policy field must be boolean: {key}")
            values[key] = value

    if "allowed_content_types" in data:
        value = data["allowed_content_types"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise CapsulePolicyError("policy field must be a list of strings: allowed_content_types")
        values["allowed_content_types"] = frozenset(value)

    if "required_signature_modes" in data:
        value = data["required_signature_modes"]
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            raise CapsulePolicyError("policy field must be a list of strings: required_signature_modes")
        values["required_signature_modes"] = frozenset(value)

    if "max_payload_bytes" in data:
        value = data["max_payload_bytes"]
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise CapsulePolicyError("policy field must be a non-negative integer: max_payload_bytes")
        values["max_payload_bytes"] = value

    return CapsulePolicy(**values)
