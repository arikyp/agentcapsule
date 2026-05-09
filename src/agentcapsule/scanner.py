"""Heuristic scanning for Agent Capsules and dense text risks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from agentcapsule.envelope import BEGIN_MARKER, END_MARKER, parse_envelope, verify_envelope
from agentcapsule.policy import DEFAULT_POLICY, CapsulePolicy

_BASE64_RE = re.compile(r"(?<![A-Za-z0-9+/=])(?:[A-Za-z0-9+/]{80,}={0,2})(?![A-Za-z0-9+/=])")
_ZERO_WIDTH = {"\u200b", "\u200c", "\u200d", "\ufeff", "\u2060"}
_EXCERPT_LIMIT = 96


@dataclass(frozen=True)
class ScanFinding:
    finding_type: str
    risk: str
    message: str
    line: int
    column: int
    start: int
    end: int
    excerpt: str

    def to_dict(self) -> dict[str, object]:
        return {
            "type": self.finding_type,
            "risk": self.risk,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "start": self.start,
            "end": self.end,
            "excerpt": self.excerpt,
        }


@dataclass(frozen=True)
class ScanResult:
    capsules_detected: int
    valid_capsules: int
    invalid_capsules: int
    risk_level: str
    reasons: list[str] = field(default_factory=list)
    findings: list[ScanFinding] = field(default_factory=list)


def scan_text(text: str, *, policy: CapsulePolicy = DEFAULT_POLICY) -> ScanResult:
    reasons: list[str] = []
    findings: list[ScanFinding] = []
    capsules_detected = text.count(BEGIN_MARKER)
    valid = 0
    invalid = 0

    offset = 0
    while True:
        begin = text.find(BEGIN_MARKER, offset)
        if begin < 0:
            break
        end = text.find(END_MARKER, begin)
        if end < 0:
            invalid += 1
            reasons.append("malformed capsule-like block")
            findings.append(_finding(text, "capsule_malformed", "high", "malformed capsule-like block", begin, len(text)))
            offset = begin + len(BEGIN_MARKER)
            continue
        block = text[begin : end + len(END_MARKER)]
        try:
            envelope = parse_envelope(block)
            policy.check_metadata(envelope)
            payload = verify_envelope(envelope)
            policy.check_payload(payload)
            valid += 1
        except Exception as exc:  # scanner must be resilient
            invalid += 1
            reasons.append(f"invalid capsule: {exc}")
            findings.append(_finding(text, "capsule_invalid", "high", f"invalid capsule: {exc}", begin, end))
        offset = end + len(END_MARKER)

    if BEGIN_MARKER in text and END_MARKER not in text:
        reasons.append("capsule begin marker without end marker")
    for idx, char in enumerate(text):
        if char in _ZERO_WIDTH:
            reasons.append("suspicious invisible Unicode characters")
            findings.append(
                _finding(text, "unicode_invisible", "high", "suspicious invisible Unicode character", idx, idx + 1)
            )
    dense_blocks = list(_BASE64_RE.finditer(text))
    for match in dense_blocks:
        reasons.append("high-entropy/base64-looking block")
        findings.append(
            _finding(
                text,
                "dense_base64_like",
                "medium",
                "high-entropy/base64-looking block",
                match.start(),
                match.end(),
            )
        )
    for start, end in _very_long_dense_line_spans(text):
        reasons.append("very long dense text block")
        findings.append(_finding(text, "dense_long_line", "medium", "very long dense text block", start, end))

    risk = _risk_level(invalid, dense_blocks, reasons)
    return ScanResult(
        capsules_detected=capsules_detected,
        valid_capsules=valid,
        invalid_capsules=invalid,
        risk_level=risk,
        reasons=sorted(set(reasons)),
        findings=findings,
    )


def _very_long_dense_line_spans(text: str) -> list[tuple[int, int]]:
    spans = []
    offset = 0
    for line in text.splitlines(keepends=True):
        stripped = line.strip()
        if len(stripped) >= 500 and len(stripped.split()) <= 2:
            start = offset + line.find(stripped)
            spans.append((start, start + len(stripped)))
        offset += len(line)
    return spans


def _risk_level(invalid: int, dense_blocks: list[re.Match[str]], reasons: list[str]) -> str:
    if invalid or any("invisible" in reason for reason in reasons):
        return "high"
    if dense_blocks or any("dense" in reason for reason in reasons):
        return "medium"
    return "low"


def _finding(
    text: str,
    finding_type: str,
    risk: str,
    message: str,
    start: int,
    end: int,
) -> ScanFinding:
    line, column = _line_column(text, start)
    excerpt = text[start:end].replace("\r", "\\r").replace("\n", "\\n")
    if len(excerpt) > _EXCERPT_LIMIT:
        excerpt = excerpt[: _EXCERPT_LIMIT - 3] + "..."
    return ScanFinding(
        finding_type=finding_type,
        risk=risk,
        message=message,
        line=line,
        column=column,
        start=start,
        end=end,
        excerpt=excerpt,
    )


def _line_column(text: str, index: int) -> tuple[int, int]:
    line = text.count("\n", 0, index) + 1
    previous_newline = text.rfind("\n", 0, index)
    column = index + 1 if previous_newline < 0 else index - previous_newline
    return line, column
