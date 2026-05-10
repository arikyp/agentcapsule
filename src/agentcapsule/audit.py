"""Structured audit events for Agent Capsule governance."""

from __future__ import annotations

from typing import Any

from agentcapsule.policy import CapsulePolicy, policy_to_dict

AUDIT_SCHEMA_VERSION = 1


def disposition_from_risk(risk_level: str) -> str:
    if risk_level == "high":
        return "block"
    if risk_level == "medium":
        return "review"
    return "allow"


def disposition_from_status(*, ok: bool, signature_trust: dict[str, object] | None = None) -> str:
    if not ok:
        return "block"
    if signature_trust and signature_trust.get("status") != "trusted":
        return "review"
    return "allow"


def audit_event(
    *,
    operation: str,
    disposition: str,
    policy: CapsulePolicy,
    result: dict[str, Any],
    subject: str | None = None,
    reasons: list[str] | None = None,
) -> dict[str, object]:
    return {
        "event_type": "agent_capsule_audit",
        "schema_version": AUDIT_SCHEMA_VERSION,
        "operation": operation,
        "disposition": disposition,
        "subject": subject,
        "policy": policy_to_dict(policy),
        "reasons": reasons or _reasons_from_result(result, disposition),
        "result": result,
    }


def scan_audit_event(*, report: dict[str, Any], policy: CapsulePolicy, subject: str | None = None) -> dict[str, object]:
    return audit_event(
        operation="scan",
        disposition=str(report["disposition"]),
        policy=policy,
        subject=subject,
        reasons=[str(reason) for reason in report.get("reasons", [])],
        result=report,
    )


def _reasons_from_result(result: dict[str, Any], disposition: str) -> list[str]:
    if result.get("verification") == "ok" or result.get("verification_status") == "ok":
        trust = result.get("signature_trust")
        if isinstance(trust, dict) and trust.get("status") != "trusted":
            return [str(trust.get("reason", "signature is valid but not trusted"))]
        if disposition == "allow":
            return ["operation verified successfully"]
    if result.get("verification_error"):
        return [str(result["verification_error"])]
    if disposition == "block":
        return ["operation failed policy or verification"]
    if disposition == "review":
        return ["operation requires review"]
    return []
