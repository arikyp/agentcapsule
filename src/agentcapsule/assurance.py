"""Agent Capsule V1 delegation-assurance primitives.

This module is intentionally additive and does not alter the V0 manifest or
receiver paths. It defines strict, deterministic validation and canonical JSON
encoding for V1 delegation contracts and completion receipts.
"""

from __future__ import annotations

import json
from typing import Any

from agentcapsule.errors import CapsuleParseError

V1_SCHEMA_VERSION = "1.0"
DELEGATION_CONTRACT_TYPE = "delegation_contract"
COMPLETION_RECEIPT_TYPE = "completion_receipt"
POSTCONDITION_STATUSES = {"pass", "fail", "unknown"}


def canonical_json(value: dict[str, object]) -> str:
    """Return deterministic JSON after validating the V1 assurance object."""
    validate_assurance_object(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def validate_assurance_object(value: Any) -> None:
    if not isinstance(value, dict):
        raise CapsuleParseError("assurance object must be a JSON object")

    capsule_type = value.get("capsule_type")
    if capsule_type == DELEGATION_CONTRACT_TYPE:
        validate_delegation_contract(value)
        return
    if capsule_type == COMPLETION_RECEIPT_TYPE:
        validate_completion_receipt(value)
        return
    raise CapsuleParseError("unsupported assurance capsule_type")


def validate_delegation_contract(contract: Any) -> None:
    if not isinstance(contract, dict):
        raise CapsuleParseError("delegation contract must be a JSON object")

    required = {
        "schema_version",
        "capsule_type",
        "capsule_id",
        "issuer",
        "intended_receiver",
        "issued_at",
        "delegation",
        "source_state",
        "assertions",
        "preconditions",
        "payload",
        "postconditions",
        "evidence_requirements",
        "lineage",
    }
    _require_fields(contract, required, "delegation contract")

    if contract["schema_version"] != V1_SCHEMA_VERSION:
        raise CapsuleParseError("unsupported delegation contract schema_version")
    if contract["capsule_type"] != DELEGATION_CONTRACT_TYPE:
        raise CapsuleParseError("delegation contract capsule_type is invalid")

    _require_nonempty_string(contract, "capsule_id", "delegation contract")
    _require_nonempty_string(contract, "issued_at", "delegation contract")
    _validate_identity(contract["issuer"], "issuer")
    _validate_identity(contract["intended_receiver"], "intended_receiver")

    delegation = contract["delegation"]
    if not isinstance(delegation, dict):
        raise CapsuleParseError("delegation must be an object")
    _require_fields(
        delegation,
        {"objective", "scope", "authority_refs", "constraints"},
        "delegation",
    )
    _require_nonempty_string(delegation, "objective", "delegation")
    for key in ("scope", "authority_refs", "constraints"):
        _require_list(delegation, key, "delegation")

    for key in (
        "source_state",
        "assertions",
        "preconditions",
        "postconditions",
        "evidence_requirements",
    ):
        _require_list(contract, key, "delegation contract")

    if not isinstance(contract["payload"], dict):
        raise CapsuleParseError("delegation contract payload must be an object")
    if not isinstance(contract["lineage"], dict):
        raise CapsuleParseError("delegation contract lineage must be an object")


def validate_completion_receipt(receipt: Any) -> None:
    if not isinstance(receipt, dict):
        raise CapsuleParseError("completion receipt must be a JSON object")

    required = {
        "schema_version",
        "capsule_type",
        "receipt_id",
        "capsule_id",
        "executor",
        "actions_performed",
        "evidence",
        "postcondition_results",
        "exceptions",
        "lineage",
        "completed_at",
    }
    _require_fields(receipt, required, "completion receipt")

    if receipt["schema_version"] != V1_SCHEMA_VERSION:
        raise CapsuleParseError("unsupported completion receipt schema_version")
    if receipt["capsule_type"] != COMPLETION_RECEIPT_TYPE:
        raise CapsuleParseError("completion receipt capsule_type is invalid")

    for key in ("receipt_id", "capsule_id", "completed_at"):
        _require_nonempty_string(receipt, key, "completion receipt")
    _validate_identity(receipt["executor"], "executor")

    for key in ("actions_performed", "evidence", "postcondition_results", "exceptions"):
        _require_list(receipt, key, "completion receipt")
    if not isinstance(receipt["lineage"], dict):
        raise CapsuleParseError("completion receipt lineage must be an object")

    for result in receipt["postcondition_results"]:
        _validate_postcondition_result(result)


def _validate_identity(value: Any, label: str) -> None:
    if not isinstance(value, dict):
        raise CapsuleParseError(f"{label} must be an object")
    _require_fields(value, {"id"}, label)
    _require_nonempty_string(value, "id", label)
    identity_ref = value.get("identity_ref")
    if identity_ref is not None and (not isinstance(identity_ref, str) or not identity_ref):
        raise CapsuleParseError(f"{label} identity_ref must be a non-empty string")


def _validate_postcondition_result(value: Any) -> None:
    if not isinstance(value, dict):
        raise CapsuleParseError("postcondition result must be an object")
    _require_fields(value, {"postcondition_id", "status", "evidence_refs"}, "postcondition result")
    _require_nonempty_string(value, "postcondition_id", "postcondition result")
    status = value["status"]
    if not isinstance(status, str) or status not in POSTCONDITION_STATUSES:
        raise CapsuleParseError("postcondition result status must be pass, fail, or unknown")
    _require_list(value, "evidence_refs", "postcondition result")


def _require_fields(value: dict[str, object], required: set[str], label: str) -> None:
    missing = sorted(required - set(value))
    if missing:
        raise CapsuleParseError(f"missing {label} fields: {', '.join(missing)}")


def _require_nonempty_string(value: dict[str, object], key: str, label: str) -> None:
    candidate = value.get(key)
    if not isinstance(candidate, str) or not candidate:
        raise CapsuleParseError(f"{label} field must be a non-empty string: {key}")


def _require_list(value: dict[str, object], key: str, label: str) -> None:
    if not isinstance(value.get(key), list):
        raise CapsuleParseError(f"{label} field must be a list: {key}")
