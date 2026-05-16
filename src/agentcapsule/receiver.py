"""High-level Agent Capsule receiver and ingestion helpers."""

from __future__ import annotations

import base64
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from agentcapsule.envelope import BEGIN_MARKER, END_MARKER, build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.errors import (
    CapsuleError,
    CapsuleParseError,
    CapsulePolicyError,
    CapsuleUnpackError,
    CapsuleVerificationError,
)
from agentcapsule.fetcher import fetch_capsule
from agentcapsule.manifest import (
    DEFAULT_CAPSULE_TYPE,
    DELIVERY_MODES,
    pack_path_with_manifest,
    unpack_payload,
    verify_manifest_matches_payload,
)
from agentcapsule.policy import DEFAULT_POLICY, CapsulePolicy, load_policy, policy_to_dict
from agentcapsule.scanner import scan_text as _scan_text
from agentcapsule.signing import (
    SIGNATURE_ED25519,
    SIGNATURE_HMAC_SHA256,
    SIGNATURE_NONE,
    key_from_env,
    load_private_key_file,
    load_public_key_file,
    sign_envelope,
    sign_envelope_ed25519,
    verify_ed25519_signature,
    verify_signature,
)
from agentcapsule.trust import SignatureRegistry, SignatureTrustResult, load_signature_registries, load_signature_registry


@dataclass(frozen=True)
class VerificationResult:
    payload: bytes
    payload_sha256: str
    codec: str
    content_type: str
    capsule_manifest: dict[str, object] | None
    signature_mode: str
    signature_trust: dict[str, object] | None

    def to_dict(self) -> dict[str, object]:
        return {
            "verification": "ok",
            "payload_bytes": len(self.payload),
            "payload_sha256": self.payload_sha256,
            "codec": self.codec,
            "content_type": self.content_type,
            "capsule_manifest": self.capsule_manifest,
            "signature_mode": self.signature_mode,
            "signature_trust": self.signature_trust,
        }


@dataclass(frozen=True)
class UnpackResult:
    verification: VerificationResult
    files_written: list[str]

    def to_dict(self) -> dict[str, object]:
        payload = self.verification.to_dict()
        payload["files_written"] = self.files_written
        return payload


@dataclass(frozen=True)
class IngestResult:
    inline_capsules: list[dict[str, object]]
    references: list[dict[str, object]]
    unpacked_files: list[str]
    malformed_blocks: int
    effective_policy: dict[str, object]
    scan_report: dict[str, object] | None = None

    @property
    def has_failures(self) -> bool:
        if self.malformed_blocks:
            return True
        if any(item.get("status") == "invalid" for item in self.inline_capsules):
            return True
        if any(item.get("status") in {"invalid", "failed"} for item in self.references):
            return True
        return False

    def to_dict(self) -> dict[str, object]:
        accepted_capsules_count = _count_status(self.inline_capsules, "unpacked") + _count_status(self.references, "unpacked")
        rejected_capsules_count = _count_status(self.inline_capsules, "invalid") + _count_status(
            self.references, ("invalid", "failed")
        )
        skipped_references_count = _count_status(self.references, "skipped")
        fetched_references_count = sum(1 for item in self.references if item.get("fetched") is True)
        rejected_reasons = _aggregate_rejected_reasons(self)
        return {
            "report_type": "agent_capsule_ingest_report",
            "schema_version": 1,
            "disposition": _ingest_disposition(self),
            "accepted_capsules_count": accepted_capsules_count,
            "rejected_capsules_count": rejected_capsules_count,
            "skipped_references_count": skipped_references_count,
            "fetched_references_count": fetched_references_count,
            "unpacked_files_count": len(self.unpacked_files),
            "rejected_reasons_by_type": rejected_reasons,
            "effective_policy": self.effective_policy,
            "inline_capsules": self.inline_capsules,
            "references": self.references,
            "unpacked_files": self.unpacked_files,
            "malformed_blocks": self.malformed_blocks,
            "scan_report": self.scan_report,
        }


def pack_path(
    path: str | Path,
    *,
    out: str | Path,
    codec: str = "base64",
    created_by: str = "local",
    capsule_type: str = DEFAULT_CAPSULE_TYPE,
    task_id: str = "",
    delivery_mode: str = "inline",
    delivery_uri: str | None = None,
    compression: str = "none",
    sign_key_env: str | None = None,
    sign_ed25519_key: str | Path | None = None,
    signature_key_id: str | None = None,
    no_inline_public_key: bool = False,
    encrypt: str | None = None,
    encryption_key_env: str | None = None,
    encryption_key_id: str | None = None,
) -> dict[str, object]:
    if sign_key_env and sign_ed25519_key:
        raise CapsuleError("choose only one signature mode")
    if delivery_mode not in DELIVERY_MODES:
        raise CapsuleError(f"unsupported delivery mode: {delivery_mode}")

    encryption_key = None
    if encrypt:
        if encrypt != "aes-256-gcm":
            raise CapsuleError(f"unsupported encryption mode: {encrypt}")
        if not encryption_key_env:
            raise CapsuleError("--encrypt aes-256-gcm requires encryption_key_env")
        encryption_key = _encryption_key_from_env(encryption_key_env)

    packed = pack_path_with_manifest(Path(path))
    envelope = build_envelope(
        packed.payload,
        codec=codec,
        content_type=packed.content_type,
        filename=packed.filename,
        created_by=created_by,
        capsule_type=capsule_type,
        task_id=task_id,
        manifest_files=packed.manifest_files,
        delivery_mode=delivery_mode,
        delivery_uri=delivery_uri,
        compression=compression,
        encryption_key=encryption_key,
        encryption_key_id=encryption_key_id,
    )

    if sign_key_env:
        envelope = sign_envelope(
            envelope,
            key=key_from_env(sign_key_env),
            key_id=signature_key_id,
        )
    if sign_ed25519_key:
        envelope = sign_envelope_ed25519(
            envelope,
            private_key_bytes=load_private_key_file(Path(sign_ed25519_key)),
            key_id=signature_key_id,
            inline_public_key=not no_inline_public_key,
        )

    out_path = Path(out)
    out_path.write_text(render_envelope(envelope), encoding="utf-8", newline="\n")
    return {
        "capsule": str(out_path),
        "payload_sha256": envelope.payload_sha256,
        "codec": envelope.codec,
        "content_type": envelope.content_type,
        "delivery_mode": delivery_mode,
    }


def verify_capsule(
    capsule: str | Path,
    *,
    policy: CapsulePolicy | str | Path | None = None,
    key_env: str | None = None,
    encryption_key_env: str | None = None,
    ed25519_public_key: str | Path | None = None,
    signature_registry: SignatureRegistry | str | Path | Sequence[str | Path] | None = None,
) -> VerificationResult:
    envelope = parse_envelope(_capsule_text(capsule))
    policy_obj = _resolve_policy(policy)
    registry = _resolve_signature_registry(signature_registry)

    policy_obj.check_metadata(envelope)
    trust = _verify_signature(
        envelope,
        key_env=key_env,
        ed25519_public_key=ed25519_public_key,
        signature_registry=registry,
    )
    policy_obj.check_signature_trust(trust.status if trust else None)

    payload = verify_envelope(envelope, encryption_key=_encryption_key_from_env_optional(encryption_key_env))
    policy_obj.check_payload(payload)
    capsule_manifest = envelope.capsule_manifest
    verify_manifest_matches_payload(
        manifest=capsule_manifest,
        payload=payload,
        content_type=envelope.content_type,
        filename=envelope.headers.get("filename"),
    )
    return VerificationResult(
        payload=payload,
        payload_sha256=envelope.payload_sha256,
        codec=envelope.codec,
        content_type=envelope.content_type,
        capsule_manifest=capsule_manifest,
        signature_mode=envelope.headers.get("signature", SIGNATURE_NONE),
        signature_trust=trust.to_dict() if trust else None,
    )


def unpack_capsule(
    capsule: str | Path,
    *,
    out_dir: str | Path,
    policy: CapsulePolicy | str | Path | None = None,
    key_env: str | None = None,
    encryption_key_env: str | None = None,
    ed25519_public_key: str | Path | None = None,
    signature_registry: SignatureRegistry | str | Path | Sequence[str | Path] | None = None,
) -> UnpackResult:
    verification = verify_capsule(
        capsule,
        policy=policy,
        key_env=key_env,
        encryption_key_env=encryption_key_env,
        ed25519_public_key=ed25519_public_key,
        signature_registry=signature_registry,
    )
    envelope = parse_envelope(_capsule_text(capsule))
    written = unpack_payload(
        verification.payload,
        envelope.content_type,
        Path(out_dir),
        filename=envelope.headers.get("filename"),
    )
    return UnpackResult(
        verification=verification,
        files_written=[str(path) for path in written],
    )


def scan_text(
    text: str,
    *,
    policy: CapsulePolicy | str | Path | None = None,
    signature_registry: SignatureRegistry | str | Path | Sequence[str | Path] | None = None,
    encryption_key_env: str | None = None,
):
    encryption_key = _encryption_key_from_env_optional(encryption_key_env)
    return _scan_text(
        text,
        policy=_resolve_policy(policy),
        signature_registry=_resolve_signature_registry(signature_registry),
        encryption_key=encryption_key,
    )


def ingest_messages(
    messages: Sequence[object] | str,
    *,
    out_dir: str | Path,
    policy: CapsulePolicy | str | Path | None = None,
    key_env: str | None = None,
    encryption_key_env: str | None = None,
    ed25519_public_key: str | Path | None = None,
    signature_registry: SignatureRegistry | str | Path | Sequence[str | Path] | None = None,
    fetch_references: bool = True,
    resumable_fetch: bool = False,
    include_scan_report: bool = True,
) -> IngestResult:
    policy_obj = _resolve_policy(policy)
    registry = _resolve_signature_registry(signature_registry)
    out_root = Path(out_dir)
    out_root.mkdir(parents=True, exist_ok=True)

    inline_capsules: list[dict[str, object]] = []
    references: list[dict[str, object]] = []
    unpacked_files: list[str] = []
    malformed_blocks = 0

    message_texts = _coerce_messages(messages)
    ingest_scan_report = None
    scan_encryption_key = None
    if encryption_key_env:
        try:
            scan_encryption_key = _encryption_key_from_env(encryption_key_env)
        except CapsuleError:
            scan_encryption_key = None
    if include_scan_report:
        ingest_scan_report = _scan_report(
            _scan_text(
                "\n".join(message_texts),
                policy=policy_obj,
                signature_registry=registry,
                encryption_key=scan_encryption_key,
            ),
            policy_obj,
        )
    for index, text in enumerate(message_texts):
        blocks, malformed = _extract_inline_capsule_blocks(text)
        malformed_blocks += malformed

        for block_idx, block in enumerate(blocks):
            capsule_sha256 = hashlib.sha256(block.encode("utf-8")).hexdigest()
            try:
                target_dir = out_root / "inline" / f"message-{index:04d}-capsule-{block_idx:04d}"
                unpacked = unpack_capsule(
                    block,
                    out_dir=target_dir,
                    policy=policy_obj,
                    key_env=key_env,
                    encryption_key_env=encryption_key_env,
                    ed25519_public_key=ed25519_public_key,
                    signature_registry=registry,
                )
                inline_payload = {
                    "message_index": index,
                    "capsule_index": block_idx,
                    "capsule_sha256": capsule_sha256,
                    "status": "unpacked",
                    "accepted": True,
                    "stage": "unpack",
                    "reason_code": None,
                    "reason_message": None,
                    **unpacked.to_dict(),
                }
                unpacked_files.extend(unpacked.files_written)
            except Exception as exc:  # receiver path must stay resilient
                stage, reason_code, reason_message = _classify_ingest_exception(exc, context="inline_unpack")
                inline_payload = {
                    "message_index": index,
                    "capsule_index": block_idx,
                    "capsule_sha256": capsule_sha256,
                    "status": "invalid",
                    "accepted": False,
                    "stage": stage,
                    "reason_code": reason_code,
                    "reason_message": reason_message,
                    "error": str(exc),
                }
            inline_capsules.append(inline_payload)

        for ref_idx, descriptor in enumerate(_extract_reference_descriptors(text)):
            ref_error = _validate_reference_descriptor(descriptor)
            uri_value = descriptor.get("capsule_uri")
            expected_capsule_sha = descriptor.get("capsule_sha256")
            expected_payload_sha = descriptor.get("payload_sha256")
            ref_result: dict[str, object] = {
                "message_index": index,
                "reference_index": ref_idx,
                "descriptor": descriptor,
                "capsule_uri": str(uri_value) if isinstance(uri_value, str) else None,
                "capsule_sha256_expected": str(expected_capsule_sha) if isinstance(expected_capsule_sha, str) else None,
                "payload_sha256_expected": str(expected_payload_sha) if isinstance(expected_payload_sha, str) else None,
                "capsule_sha256_actual": None,
                "payload_sha256_actual": None,
                "status": "detected",
                "accepted": False,
                "stage": "scan",
                "reason_code": None,
                "reason_message": None,
                "fetched": False,
            }
            references.append(ref_result)

            if ref_error:
                stage, reason_code, reason_message = _classify_ingest_exception(
                    CapsuleError(ref_error),
                    context="reference_descriptor",
                )
                ref_result["status"] = "invalid"
                ref_result["stage"] = stage
                ref_result["reason_code"] = reason_code
                ref_result["reason_message"] = reason_message
                ref_result["error"] = ref_error
                continue
            if not fetch_references:
                ref_result["status"] = "skipped"
                ref_result["stage"] = "fetch"
                continue

            uri = str(descriptor["capsule_uri"])
            expected_sha = str(descriptor["capsule_sha256"]).lower()
            expected_payload_sha = str(descriptor["payload_sha256"]).lower()
            ref_capsule_dir = out_root / "references"
            ref_capsule_dir.mkdir(parents=True, exist_ok=True)
            ref_path = ref_capsule_dir / f"message-{index:04d}-ref-{ref_idx:04d}.capsule.txt"
            try:
                data = fetch_capsule(uri, expected_sha256=expected_sha, save_path=ref_path, resumable=resumable_fetch)
                actual_capsule_sha = hashlib.sha256(data).hexdigest().lower()
                ref_result["capsule_sha256_actual"] = actual_capsule_sha
                ref_result["fetched"] = True
                ref_result["stage"] = "fetch"
                capsule_text = data.decode("utf-8")
                ref_result["status"] = "fetched"
                ref_result["capsule_path"] = str(ref_path)
            except Exception as exc:  # receiver path must stay resilient
                stage, reason_code, reason_message = _classify_ingest_exception(exc, context="reference_fetch")
                ref_result["status"] = "failed"
                ref_result["stage"] = stage
                ref_result["reason_code"] = reason_code
                ref_result["reason_message"] = reason_message
                ref_result["error"] = str(exc)
                continue

            try:
                envelope = parse_envelope(capsule_text)
                actual_payload_sha = envelope.payload_sha256.lower()
                ref_result["payload_sha256_actual"] = actual_payload_sha
                if actual_payload_sha != expected_payload_sha:
                    raise CapsuleError("reference descriptor payload_sha256 does not match fetched capsule")
            except Exception as exc:  # receiver path must stay resilient
                stage, reason_code, reason_message = _classify_ingest_exception(exc, context="reference_verify")
                ref_result["status"] = "failed"
                ref_result["stage"] = stage
                ref_result["reason_code"] = reason_code
                ref_result["reason_message"] = reason_message
                ref_result["error"] = str(exc)
                continue

            try:
                target_dir = out_root / "reference-unpacked" / f"message-{index:04d}-ref-{ref_idx:04d}"
                unpacked = unpack_capsule(
                    capsule_text,
                    out_dir=target_dir,
                    policy=policy_obj,
                    key_env=key_env,
                    encryption_key_env=encryption_key_env,
                    ed25519_public_key=ed25519_public_key,
                    signature_registry=registry,
                )
                ref_result["status"] = "unpacked"
                ref_result["accepted"] = True
                ref_result["stage"] = "unpack"
                ref_result["reason_code"] = None
                ref_result["reason_message"] = None
                ref_result["verification"] = unpacked.verification.to_dict()
                ref_result["files_written"] = unpacked.files_written
                unpacked_files.extend(unpacked.files_written)
            except Exception as exc:  # receiver path must stay resilient
                stage, reason_code, reason_message = _classify_ingest_exception(exc, context="reference_unpack")
                ref_result["status"] = "failed"
                ref_result["stage"] = stage
                ref_result["reason_code"] = reason_code
                ref_result["reason_message"] = reason_message
                ref_result["error"] = str(exc)

    return IngestResult(
        inline_capsules=inline_capsules,
        references=references,
        unpacked_files=unpacked_files,
        malformed_blocks=malformed_blocks,
        effective_policy=policy_to_dict(policy_obj),
        scan_report=ingest_scan_report,
    )


def _capsule_text(capsule: str | Path) -> str:
    if isinstance(capsule, Path):
        return capsule.read_text(encoding="utf-8")
    if isinstance(capsule, str):
        candidate = Path(capsule)
        if "\n" not in capsule and candidate.exists():
            return candidate.read_text(encoding="utf-8")
        return capsule
    raise CapsuleError("capsule must be a path or capsule text")


def _resolve_policy(policy: CapsulePolicy | str | Path | None) -> CapsulePolicy:
    if policy is None:
        return DEFAULT_POLICY
    if isinstance(policy, CapsulePolicy):
        return policy
    return load_policy(Path(policy))


def _resolve_signature_registry(
    signature_registry: SignatureRegistry | str | Path | Sequence[str | Path] | None,
) -> SignatureRegistry | None:
    if signature_registry is None:
        return None
    if isinstance(signature_registry, SignatureRegistry):
        return signature_registry
    if isinstance(signature_registry, Sequence) and not isinstance(signature_registry, (str, Path)):
        return load_signature_registries([Path(path) for path in signature_registry])
    return load_signature_registry(Path(signature_registry))


def _verify_signature(
    envelope,
    *,
    key_env: str | None,
    ed25519_public_key: str | Path | None,
    signature_registry: SignatureRegistry | None,
) -> SignatureTrustResult | None:
    mode = envelope.headers.get("signature", SIGNATURE_NONE)
    if mode == SIGNATURE_NONE:
        return None
    if mode == SIGNATURE_HMAC_SHA256:
        if not key_env:
            raise CapsuleError("hmac-sha256 signature requires key_env")
        verify_signature(envelope, key=key_from_env(key_env))
        return None
    if mode != SIGNATURE_ED25519:
        raise CapsuleError(f"unsupported signature mode: {mode}")

    trust = _signature_trust(envelope, signature_registry)
    if ed25519_public_key:
        verify_ed25519_signature(envelope, public_key_bytes=load_public_key_file(Path(ed25519_public_key)))
    elif trust and trust.public_key is not None:
        verify_ed25519_signature(envelope, public_key_bytes=trust.public_key)
    else:
        verify_ed25519_signature(envelope)
    return trust


def _signature_trust(envelope, signature_registry: SignatureRegistry | None) -> SignatureTrustResult | None:
    if envelope.headers.get("signature") != SIGNATURE_ED25519:
        return None
    if signature_registry is None:
        if envelope.headers.get("signature_public_key"):
            return SignatureTrustResult(
                "untrusted",
                "inline public key is not trusted by a registry",
                envelope.headers.get("signature_key_id"),
                envelope.headers.get("signature_public_key_fingerprint"),
            )
        return None
    return signature_registry.resolve(
        key_id=envelope.headers.get("signature_key_id"),
        fingerprint=envelope.headers.get("signature_public_key_fingerprint"),
    )


def _encryption_key_from_env_optional(env_name: str | None) -> bytes | None:
    if not env_name:
        return None
    return _encryption_key_from_env(env_name)


def _encryption_key_from_env(env_name: str) -> bytes:
    raw_key = key_from_env(env_name)
    try:
        decoded = base64.b64decode(raw_key, validate=True)
    except Exception:
        decoded = raw_key
    if len(decoded) != 32:
        raise CapsuleError("encryption key must be 32 bytes (raw or base64)")
    return decoded


def _coerce_messages(messages: Sequence[object] | str) -> list[str]:
    if isinstance(messages, str):
        return [messages]
    coerced = []
    for message in messages:
        text = _extract_message_text(message)
        if text:
            coerced.append(text)
    return coerced


def _extract_message_text(message: object) -> str:
    if isinstance(message, str):
        return message
    if isinstance(message, dict):
        for key in ("content", "text", "message", "body"):
            value = message.get(key)
            if isinstance(value, str):
                return value
        content = message.get("content")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    text = item.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "\n".join(parts)
    return ""


def _extract_inline_capsule_blocks(text: str) -> tuple[list[str], int]:
    blocks: list[str] = []
    malformed = 0
    offset = 0
    while True:
        begin = text.find(BEGIN_MARKER, offset)
        if begin < 0:
            break
        end = text.find(END_MARKER, begin + len(BEGIN_MARKER))
        if end < 0:
            malformed += 1
            offset = begin + len(BEGIN_MARKER)
            continue
        blocks.append(text[begin : end + len(END_MARKER)])
        offset = end + len(END_MARKER)
    return blocks, malformed


def _extract_reference_descriptors(text: str) -> list[dict[str, object]]:
    decoder = json.JSONDecoder()
    descriptors: list[dict[str, object]] = []
    offset = 0
    while True:
        brace = text.find("{", offset)
        if brace < 0:
            return descriptors
        try:
            obj, end = decoder.raw_decode(text, brace)
        except json.JSONDecodeError:
            offset = brace + 1
            continue
        offset = end
        if isinstance(obj, dict) and obj.get("reference_type") == "agent_capsule_reference":
            descriptors.append(obj)


def _validate_reference_descriptor(descriptor: dict[str, object]) -> str | None:
    required_fields = ("reference_type", "capsule_uri", "capsule_sha256", "payload_sha256")
    for field in required_fields:
        value = descriptor.get(field)
        if not isinstance(value, str) or not value:
            return f"reference descriptor missing valid field: {field}"
    for field in ("capsule_sha256", "payload_sha256"):
        sha = str(descriptor[field])
        if len(sha) != 64:
            return f"reference descriptor {field} must be a SHA256 hex string"
        try:
            int(sha, 16)
        except ValueError:
            return f"reference descriptor {field} must be a SHA256 hex string"
    return None


def _ingest_disposition(result: IngestResult) -> str:
    risk_level = "low"
    if isinstance(result.scan_report, dict):
        risk_raw = result.scan_report.get("risk_level")
        if isinstance(risk_raw, str):
            risk_level = risk_raw
    if result.has_failures or risk_level == "high":
        return "block"
    if risk_level == "medium":
        return "review"
    return "allow"


def _count_status(items: list[dict[str, object]], status: str | tuple[str, ...]) -> int:
    if isinstance(status, str):
        status_values = {status}
    else:
        status_values = set(status)
    return sum(1 for item in items if item.get("status") in status_values)


def _aggregate_rejected_reasons(result: IngestResult) -> dict[str, int]:
    counts: dict[str, int] = {}
    if result.malformed_blocks:
        counts["MALFORMED_CAPSULE_BLOCK"] = result.malformed_blocks
    for item in result.inline_capsules:
        if item.get("status") != "invalid":
            continue
        reason = item.get("reason_code")
        if isinstance(reason, str):
            counts[reason] = counts.get(reason, 0) + 1
    for item in result.references:
        if item.get("status") not in {"invalid", "failed"}:
            continue
        reason = item.get("reason_code")
        if isinstance(reason, str):
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def _classify_ingest_exception(exc: Exception, *, context: str) -> tuple[str, str, str]:
    message = str(exc)
    lowered = message.lower()

    if context == "reference_descriptor":
        return "scan", "REFERENCE_DESCRIPTOR_INVALID", message
    if context == "reference_fetch" and "fetched capsule sha256 mismatch" in lowered:
        return "fetch", "REFERENCE_CAPSULE_HASH_MISMATCH", message
    if context == "reference_fetch":
        if _is_fetch_policy_error(lowered):
            return "fetch", "FETCH_BLOCKED_BY_POLICY", message
        return "fetch", "REFERENCE_TRANSPORT_ERROR", message
    if context == "reference_verify" and "payload_sha256 does not match fetched capsule" in lowered:
        return "verify", "REFERENCE_PAYLOAD_HASH_MISMATCH", message

    if isinstance(exc, CapsuleParseError):
        return "parse", "CAPSULE_PARSE_ERROR", message
    if isinstance(exc, CapsuleUnpackError):
        return "unpack", "UNPACK_FAILED", message
    if isinstance(exc, CapsulePolicyError):
        if "signature key is not trusted" in lowered or "inline public keys are not allowed" in lowered:
            return "policy", "SIGNATURE_UNTRUSTED", message
        if "unsigned capsules are not allowed" in lowered or "signature mode is not allowed" in lowered:
            return "policy", "SIGNATURE_REQUIRED", message
        return "policy", "POLICY_BLOCK", message
    if isinstance(exc, CapsuleVerificationError):
        if "payload sha256 mismatch" in lowered:
            return "verify", "PAYLOAD_HASH_MISMATCH", message
        if "decryption key provided" in lowered:
            return "verify", "ENCRYPTION_KEY_MISSING", message
        if "decryption failed" in lowered:
            return "verify", "DECRYPTION_FAILED", message
        if "signature verification failed" in lowered:
            return "verify", "SIGNATURE_UNTRUSTED", message
    if isinstance(exc, CapsuleError):
        if "signature requires key_env" in lowered:
            return "verify", "SIGNATURE_REQUIRED", message
        if "payload_sha256 does not match fetched capsule" in lowered:
            return "verify", "REFERENCE_PAYLOAD_HASH_MISMATCH", message

    if context == "reference_unpack":
        return "unpack", "UNPACK_FAILED", message
    if context == "inline_unpack":
        if "payload sha256 mismatch" in lowered:
            return "verify", "PAYLOAD_HASH_MISMATCH", message
        return "unknown", "UNKNOWN_ERROR", message
    return "unknown", "UNKNOWN_ERROR", message


def _is_fetch_policy_error(lowered_message: str) -> bool:
    return (
        "unsupported uri scheme" in lowered_message
        or "missing uri host" in lowered_message
        or "blocked private or local network host" in lowered_message
    )


def _scan_report(result, policy: CapsulePolicy) -> dict[str, object]:
    return {
        "report_type": "agent_capsule_governance_scan",
        "schema_version": 1,
        "disposition": _scan_disposition(result.risk_level),
        "capsules_detected": result.capsules_detected,
        "valid_capsules": result.valid_capsules,
        "invalid_capsules": result.invalid_capsules,
        "risk_level": result.risk_level,
        "reasons": result.reasons,
        "policy": policy_to_dict(policy),
        "findings": [finding.to_dict() for finding in result.findings],
    }


def _scan_disposition(risk_level: str) -> str:
    if risk_level == "high":
        return "block"
    if risk_level == "medium":
        return "review"
    return "allow"
