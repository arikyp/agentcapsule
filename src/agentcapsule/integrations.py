"""Stable framework integration adapter built on the receiver ingest path."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from agentcapsule.policy import CapsulePolicy
from agentcapsule.receiver import IngestResult, ingest_messages
from agentcapsule.trust import SignatureRegistry

FRAMEWORK_REPORT_TYPE = "agent_capsule_framework_ingest_report"
FRAMEWORK_SCHEMA_VERSION = 1


@dataclass(frozen=True)
class FrameworkIngestResult:
    """Normalized ingest payload for framework orchestration and policy gates."""

    report_type: str
    schema_version: int
    disposition: str
    accepted_capsules_count: int
    rejected_capsules_count: int
    rejected_reasons_by_type: dict[str, int]
    unpacked_files_count: int
    unpacked_files: list[str]
    inline_capsules: list[dict[str, object]]
    references: list[dict[str, object]]
    malformed_blocks: int
    effective_policy: dict[str, object]
    scan_report: dict[str, object] | None

    @property
    def blocked(self) -> bool:
        return self.disposition == "block"

    @property
    def review_required(self) -> bool:
        return self.disposition == "review"

    def to_dict(self) -> dict[str, object]:
        return {
            "report_type": self.report_type,
            "schema_version": self.schema_version,
            "disposition": self.disposition,
            "accepted_capsules_count": self.accepted_capsules_count,
            "rejected_capsules_count": self.rejected_capsules_count,
            "rejected_reasons_by_type": dict(self.rejected_reasons_by_type),
            "unpacked_files_count": self.unpacked_files_count,
            "unpacked_files": list(self.unpacked_files),
            "inline_capsules": list(self.inline_capsules),
            "references": list(self.references),
            "malformed_blocks": self.malformed_blocks,
            "effective_policy": dict(self.effective_policy),
            "scan_report": self.scan_report,
        }


def ingest_for_framework(
    *,
    messages: Sequence[object] | str,
    out_dir: str | Path,
    policy: CapsulePolicy | str | Path | None = None,
    key_env: str | None = None,
    encryption_key_env: str | None = None,
    ed25519_public_key: str | Path | None = None,
    signature_registry: SignatureRegistry | str | Path | None = None,
    fetch_references: bool = True,
    resumable_fetch: bool = False,
    include_scan_report: bool = True,
) -> FrameworkIngestResult:
    """Run ingestion through the canonical receiver path and return stable framework output."""
    result = ingest_messages(
        messages=messages,
        out_dir=out_dir,
        policy=policy,
        key_env=key_env,
        encryption_key_env=encryption_key_env,
        ed25519_public_key=ed25519_public_key,
        signature_registry=signature_registry,
        fetch_references=fetch_references,
        resumable_fetch=resumable_fetch,
        include_scan_report=include_scan_report,
    )
    return _framework_result_from_ingest(result)


def _framework_result_from_ingest(result: IngestResult) -> FrameworkIngestResult:
    payload = result.to_dict()
    return FrameworkIngestResult(
        report_type=FRAMEWORK_REPORT_TYPE,
        schema_version=FRAMEWORK_SCHEMA_VERSION,
        disposition=str(payload["disposition"]),
        accepted_capsules_count=int(payload["accepted_capsules_count"]),
        rejected_capsules_count=int(payload["rejected_capsules_count"]),
        rejected_reasons_by_type=dict(payload["rejected_reasons_by_type"]),
        unpacked_files_count=int(payload["unpacked_files_count"]),
        unpacked_files=[str(path) for path in payload["unpacked_files"]],
        inline_capsules=list(payload["inline_capsules"]),
        references=list(payload["references"]),
        malformed_blocks=int(payload["malformed_blocks"]),
        effective_policy=dict(payload["effective_policy"]),
        scan_report=payload.get("scan_report") if isinstance(payload.get("scan_report"), dict) else None,
    )
