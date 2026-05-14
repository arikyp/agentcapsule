"""Framework integrations for Agent Capsule."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

from agentcapsule.envelope import build_envelope, parse_envelope, verify_envelope
from agentcapsule.manifest import pack_path_with_manifest, unpack_payload

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
