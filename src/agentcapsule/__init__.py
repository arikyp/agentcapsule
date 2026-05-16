"""Agent Capsule Protocol V0."""

from agentcapsule.envelope import CapsuleEnvelope, build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.integrations import (
    FRAMEWORK_REPORT_TYPE,
    FRAMEWORK_SCHEMA_VERSION,
    FrameworkIngestResult,
    ingest_for_framework,
)
from agentcapsule.receiver import (
    IngestResult,
    UnpackResult,
    VerificationResult,
    ingest_messages,
    pack_path,
    scan_text,
    unpack_capsule,
    verify_capsule,
)

__all__ = [
    "CapsuleEnvelope",
    "FRAMEWORK_REPORT_TYPE",
    "FRAMEWORK_SCHEMA_VERSION",
    "FrameworkIngestResult",
    "IngestResult",
    "UnpackResult",
    "VerificationResult",
    "build_envelope",
    "ingest_for_framework",
    "ingest_messages",
    "pack_path",
    "parse_envelope",
    "render_envelope",
    "scan_text",
    "unpack_capsule",
    "verify_capsule",
    "verify_envelope",
]
