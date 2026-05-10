#!/usr/bin/env python3
"""Evaluate an Agent A to Agent B handoff transcript and JSONL trace."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BEGIN_MARKER = "-----BEGIN AGENT CAPSULE-----"
END_MARKER = "-----END AGENT CAPSULE-----"
REPORT_TYPE = "agent_handoff_transcript_evaluation"
SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Check:
    check_id: str
    status: str
    severity: str
    message: str
    evidence: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.check_id,
            "status": self.status,
            "severity": self.severity,
            "message": self.message,
            "evidence": self.evidence,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--events", required=True, help="events.jsonl from the handoff experiment")
    parser.add_argument("--message", help="text message containing readable handoff summary plus capsule")
    parser.add_argument("--out", help="write evaluation JSON to this path")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON")
    args = parser.parse_args(argv)

    report = evaluate_transcript(
        events_path=Path(args.events),
        message_path=Path(args.message) if args.message else None,
    )
    output = json.dumps(
        report,
        indent=2 if args.pretty else None,
        sort_keys=True,
        separators=None if args.pretty else (",", ":"),
    )
    if args.out:
        Path(args.out).write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["disposition"] in {"allow", "review"} else 1


def evaluate_transcript(*, events_path: Path, message_path: Path | None = None) -> dict[str, Any]:
    events = load_events(events_path)
    message_text = message_path.read_text(encoding="utf-8") if message_path else ""
    checks = build_checks(events=events, message_text=message_text, message_path=message_path)
    disposition = disposition_for_checks(checks)
    score = score_checks(checks)
    trace_ids = sorted({str(event["trace_id"]) for event in events if isinstance(event.get("trace_id"), str)})
    report = {
        "report_type": REPORT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "disposition": disposition,
        "score": score,
        "events_path": str(events_path),
        "message_path": str(message_path) if message_path else None,
        "trace_ids": trace_ids,
        "checks": [check.to_dict() for check in checks],
        "summary": {
            "events": len(events),
            "passed_checks": sum(1 for check in checks if check.status == "pass"),
            "warning_checks": sum(1 for check in checks if check.status == "warn"),
            "failed_checks": sum(1 for check in checks if check.status == "fail"),
        },
    }
    return report


def load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"invalid JSONL at line {line_number}: {exc}") from exc
        if not isinstance(event, dict):
            raise SystemExit(f"invalid JSONL at line {line_number}: event must be an object")
        events.append(event)
    return events


def build_checks(
    *,
    events: list[dict[str, Any]],
    message_text: str,
    message_path: Path | None,
) -> list[Check]:
    scan = event_by_step(events, "scan_text_message")
    verify = event_by_step(events, "verify_handoff_capsule")
    unpack = event_by_step(events, "unpack_handoff_bundle")
    compare = event_by_operation(events, "compare_decoded_artifacts")

    return [
        check_trace_present(events),
        check_trace_id_consistency(events),
        check_readable_summary(message_text, message_path),
        check_capsule_present(message_text, message_path),
        check_scan_event(scan),
        check_verify_event(verify),
        check_trusted_signature(verify),
        check_unpack_event(unpack),
        check_artifact_compare(compare),
        check_no_block_events(events),
    ]


def check_trace_present(events: list[dict[str, Any]]) -> Check:
    if events:
        return passed("trace_present", "required", "events.jsonl contains handoff evidence", {"events": len(events)})
    return failed("trace_present", "required", "events.jsonl is empty", {"events": 0})


def check_trace_id_consistency(events: list[dict[str, Any]]) -> Check:
    trace_ids = sorted({str(event["trace_id"]) for event in events if isinstance(event.get("trace_id"), str)})
    if len(trace_ids) == 1:
        return passed("trace_id_consistent", "advisory", "all events share one trace id", {"trace_id": trace_ids[0]})
    if not trace_ids:
        return warned("trace_id_consistent", "advisory", "events do not include a trace id", {"trace_ids": []})
    return warned("trace_id_consistent", "advisory", "events contain multiple trace ids", {"trace_ids": trace_ids})


def check_readable_summary(message_text: str, message_path: Path | None) -> Check:
    if not message_path:
        return warned("readable_summary_present", "advisory", "message transcript was not provided", {})
    has_summary = "Human-readable summary:" in message_text and message_text.find(BEGIN_MARKER) > 0
    if has_summary:
        return passed(
            "readable_summary_present",
            "required",
            "message includes readable summary before capsule",
            {"message_path": str(message_path)},
        )
    return failed(
        "readable_summary_present",
        "required",
        "message is missing readable summary before capsule",
        {"message_path": str(message_path)},
    )


def check_capsule_present(message_text: str, message_path: Path | None) -> Check:
    if not message_path:
        return warned("capsule_envelope_present", "advisory", "message transcript was not provided", {})
    begins = message_text.count(BEGIN_MARKER)
    ends = message_text.count(END_MARKER)
    if begins == 1 and ends == 1 and message_text.find(BEGIN_MARKER) < message_text.find(END_MARKER):
        return passed(
            "capsule_envelope_present",
            "required",
            "message contains one complete Agent Capsule envelope",
            {"begin_markers": begins, "end_markers": ends},
        )
    return failed(
        "capsule_envelope_present",
        "required",
        "message does not contain exactly one complete Agent Capsule envelope",
        {"begin_markers": begins, "end_markers": ends},
    )


def check_scan_event(scan: dict[str, Any] | None) -> Check:
    if not scan:
        return failed("scan_event_present", "required", "scan audit event is missing", {})
    result = as_dict(scan.get("result"))
    valid_capsules = result.get("valid_capsules")
    risk_level = result.get("risk_level")
    disposition = scan.get("disposition")
    if valid_capsules and disposition in {"allow", "review"} and risk_level in {"low", "medium"}:
        return passed(
            "scan_event_present",
            "required",
            "message scan found a valid capsule and no blocking risk",
            {"disposition": disposition, "risk_level": risk_level, "valid_capsules": valid_capsules},
        )
    return failed(
        "scan_event_present",
        "required",
        "message scan did not produce acceptable capsule evidence",
        {"disposition": disposition, "risk_level": risk_level, "valid_capsules": valid_capsules},
    )


def check_verify_event(verify: dict[str, Any] | None) -> Check:
    if not verify:
        return failed("verify_event_present", "required", "verify audit event is missing", {})
    result = as_dict(verify.get("result"))
    if verify.get("disposition") == "allow" and result.get("verification") == "ok":
        return passed(
            "verify_event_present",
            "required",
            "capsule verification passed",
            {"payload_sha256": result.get("payload_sha256"), "content_type": result.get("content_type")},
        )
    return failed(
        "verify_event_present",
        "required",
        "capsule verification did not pass",
        {"disposition": verify.get("disposition"), "verification": result.get("verification")},
    )


def check_trusted_signature(verify: dict[str, Any] | None) -> Check:
    if not verify:
        return failed("trusted_signature_present", "required", "verify audit event is missing", {})
    trust = as_dict(as_dict(verify.get("result")).get("signature_trust"))
    if trust.get("status") == "trusted":
        return passed(
            "trusted_signature_present",
            "required",
            "capsule signature is valid and trusted by registry",
            {"key_id": trust.get("key_id"), "fingerprint": trust.get("fingerprint")},
        )
    return failed(
        "trusted_signature_present",
        "required",
        "capsule signature is not registry-trusted",
        {"signature_trust": trust or None},
    )


def check_unpack_event(unpack: dict[str, Any] | None) -> Check:
    if not unpack:
        return failed("unpack_event_present", "required", "unpack audit event is missing", {})
    result = as_dict(unpack.get("result"))
    files_written = result.get("files_written")
    if unpack.get("disposition") == "allow" and isinstance(files_written, list) and files_written:
        return passed(
            "unpack_event_present",
            "required",
            "capsule unpacked into sandbox output",
            {"files_written": len(files_written)},
        )
    return failed(
        "unpack_event_present",
        "required",
        "capsule unpack did not produce files",
        {"disposition": unpack.get("disposition"), "files_written": files_written},
    )


def check_artifact_compare(compare: dict[str, Any] | None) -> Check:
    if not compare:
        return failed("artifact_compare_passed", "required", "artifact comparison event is missing", {})
    result = as_dict(compare.get("result"))
    if compare.get("disposition") == "allow" and result.get("match") is True:
        return passed(
            "artifact_compare_passed",
            "required",
            "decoded artifacts match Agent A source artifacts",
            {"source_files": sorted(as_dict(result.get("source_files")).keys())},
        )
    return failed(
        "artifact_compare_passed",
        "required",
        "decoded artifacts do not match source artifacts",
        {
            "missing": result.get("missing"),
            "extra": result.get("extra"),
            "mismatched": result.get("mismatched"),
        },
    )


def check_no_block_events(events: list[dict[str, Any]]) -> Check:
    blocked = [
        event.get("step") or event.get("operation") or event.get("event_type")
        for event in events
        if event.get("disposition") == "block"
    ]
    if not blocked:
        return passed("no_block_events", "required", "trace contains no block decisions", {})
    return failed("no_block_events", "required", "trace contains block decisions", {"blocked": blocked})


def event_by_step(events: list[dict[str, Any]], step: str) -> dict[str, Any] | None:
    return next((event for event in events if event.get("step") == step), None)


def event_by_operation(events: list[dict[str, Any]], operation: str) -> dict[str, Any] | None:
    return next((event for event in events if event.get("operation") == operation), None)


def disposition_for_checks(checks: list[Check]) -> str:
    if any(check.status == "fail" and check.severity == "required" for check in checks):
        return "block"
    if any(check.status in {"fail", "warn"} for check in checks):
        return "review"
    return "allow"


def score_checks(checks: list[Check]) -> int:
    if not checks:
        return 0
    points = 0
    for check in checks:
        if check.status == "pass":
            points += 10
        elif check.status == "warn":
            points += 5
    return round((points / (len(checks) * 10)) * 100)


def passed(check_id: str, severity: str, message: str, evidence: dict[str, Any]) -> Check:
    return Check(check_id, "pass", severity, message, evidence)


def warned(check_id: str, severity: str, message: str, evidence: dict[str, Any]) -> Check:
    return Check(check_id, "warn", severity, message, evidence)


def failed(check_id: str, severity: str, message: str, evidence: dict[str, Any]) -> Check:
    return Check(check_id, "fail", severity, message, evidence)


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


if __name__ == "__main__":
    raise SystemExit(main())

