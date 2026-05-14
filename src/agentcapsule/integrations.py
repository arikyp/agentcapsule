"""Framework integrations for Agent Capsule."""

from __future__ import annotations

import os
import json
import hashlib
from pathlib import Path
from typing import Any, TYPE_CHECKING
from urllib.parse import urlparse
from urllib.request import urlopen

from agentcapsule.envelope import build_envelope, parse_envelope, verify_envelope
from agentcapsule.manifest import pack_path_with_manifest, unpack_payload
from agentcapsule.scanner import scan_text

if TYPE_CHECKING:
    from agentcapsule.envelope import CapsuleEnvelope


class LangGraphIntegration:
    """Helper for LangGraph agent handoffs using Agent Capsules."""

    @staticmethod
    def create_handoff_message(
        path: str | Path,
        *,
        created_by: str,
        task_id: str = "",
        encryption_key: bytes | None = None,
        sign_ed25519_key: Path | None = None,
    ) -> dict[str, Any]:
        """Pack a path into a capsule and return a LangGraph-compatible message."""
        from agentcapsule.signing import sign_envelope_ed25519, load_private_key_file
        
        packed = pack_path_with_manifest(Path(path))
        envelope = build_envelope(
            packed.payload,
            content_type=packed.content_type,
            filename=packed.filename,
            created_by=created_by,
            task_id=task_id,
            manifest_files=packed.manifest_files,
            encryption_key=encryption_key,
        )
        
        if sign_ed25519_key:
            envelope = sign_envelope_ed25519(
                envelope,
                private_key_bytes=load_private_key_file(sign_ed25519_key),
            )
            
        from agentcapsule.envelope import render_envelope
        capsule_text = render_envelope(envelope)
        
        return {
            "messages": [
                {
                    "role": "system",
                    "content": f"AGENT CAPSULE HANDOFF\n\n{capsule_text}",
                    "name": "capsule_orchestrator"
                }
            ]
        }

    @staticmethod
    def unpack_handoff(
        message_content: str,
        out_dir: str | Path,
        *,
        encryption_key: bytes | None = None,
    ) -> list[Path]:
        """Extract and unpack a capsule from a message string."""
        envelope = parse_envelope(message_content)
        payload = verify_envelope(envelope, encryption_key=encryption_key)
        return unpack_payload(
            payload,
            envelope.content_type,
            Path(out_dir),
            filename=envelope.headers.get("filename"),
        )


class AutoIngest:
    """Helpers to ingest inline and reference capsules from message history."""

    @staticmethod
    def scan_history(messages: list[str]) -> list[CapsuleEnvelope]:
        """Scan message history for inline capsule envelopes."""
        envelopes: list[CapsuleEnvelope] = []
        for message in messages:
            result = scan_text(message)
            envelopes.extend(result.envelopes)
        return envelopes

    @staticmethod
    def fetch_from_history(messages: list[str]) -> list[dict[str, Any]]:
        """Fetch capsule references from history and return verified summaries."""
        fetched: list[dict[str, Any]] = []
        for message in messages:
            for descriptor in _extract_reference_descriptors(message):
                capsule_text = _fetch_capsule_text(descriptor["capsule_uri"])
                capsule_sha256 = hashlib.sha256(capsule_text.encode("utf-8")).hexdigest()
                if capsule_sha256 != descriptor["capsule_sha256"]:
                    raise ValueError(f"capsule sha256 mismatch for {descriptor['capsule_uri']}")
                envelope = parse_envelope(capsule_text)
                payload = verify_envelope(envelope)
                if envelope.payload_sha256 != descriptor["payload_sha256"]:
                    raise ValueError(f"payload sha256 mismatch for {descriptor['capsule_uri']}")
                fetched.append(
                    {
                        "capsule_uri": descriptor["capsule_uri"],
                        "capsule_sha256": capsule_sha256,
                        "payload_sha256": envelope.payload_sha256,
                        "content_type": envelope.content_type,
                        "codec": envelope.codec,
                        "capsule_manifest": envelope.capsule_manifest,
                        "payload_bytes": len(payload),
                    }
                )
        return fetched

    @staticmethod
    def ingest_thread(messages: list[str]) -> dict[str, Any]:
        """Convenience method returning both inline and reference ingestion results."""
        return {
            "inline_envelopes": AutoIngest.scan_history(messages),
            "fetched_references": AutoIngest.fetch_from_history(messages),
        }


def _extract_reference_descriptors(text: str) -> list[dict[str, str]]:
    descriptors: list[dict[str, str]] = []
    decoder = json.JSONDecoder()
    index = 0
    while index < len(text):
        start = text.find("{", index)
        if start < 0:
            break
        try:
            obj, end = decoder.raw_decode(text[start:])
        except json.JSONDecodeError:
            index = start + 1
            continue
        index = start + end
        if not isinstance(obj, dict):
            continue
        if obj.get("reference_type") != "agent_capsule_reference":
            continue
        capsule_uri = obj.get("capsule_uri")
        capsule_sha256 = obj.get("capsule_sha256")
        payload_sha256 = obj.get("payload_sha256")
        if not isinstance(capsule_uri, str) or not isinstance(capsule_sha256, str) or not isinstance(payload_sha256, str):
            continue
        descriptors.append(
            {
                "capsule_uri": capsule_uri,
                "capsule_sha256": capsule_sha256,
                "payload_sha256": payload_sha256,
            }
        )
    return descriptors


def _fetch_capsule_text(uri: str) -> str:
    parsed = urlparse(uri)
    if parsed.scheme in {"http", "https", "file"}:
        with urlopen(uri, timeout=15) as response:  # nosec B310 - explicit URI scheme allowlist
            return response.read().decode("utf-8")
    raise ValueError(f"unsupported capsule_uri scheme: {parsed.scheme}")
