import unittest

from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.scanner import scan_text


class AgentCapsuleScanTests(unittest.TestCase):
    def test_scan_detects_explicit_capsule(self) -> None:
        text = "handoff follows\n" + render_envelope(build_envelope(b"payload"))
        result = scan_text(text)

        self.assertEqual(result.capsules_detected, 1)
        self.assertEqual(result.valid_capsules, 1)

    def test_scan_flags_suspicious_base64_like_block(self) -> None:
        text = "prefix\n" + ("A" * 120) + "\nsuffix\n"
        result = scan_text(text)

        self.assertEqual(result.risk_level, "medium")
        self.assertIn("high-entropy/base64-looking block", result.reasons)
        self.assertEqual(result.findings[0].finding_type, "dense_base64_like")
        self.assertEqual(result.findings[0].risk, "medium")
        self.assertEqual(result.findings[0].line, 2)
        self.assertEqual(result.findings[0].column, 1)
        self.assertLessEqual(len(result.findings[0].excerpt), 96)

    def test_scan_flags_invalid_capsule_with_location(self) -> None:
        text = "before\n-----BEGIN AGENT CAPSULE-----\ncodec: base64\n-----END AGENT CAPSULE-----\n"
        result = scan_text(text)

        self.assertEqual(result.risk_level, "high")
        self.assertEqual(result.invalid_capsules, 1)
        self.assertEqual(result.findings[0].finding_type, "capsule_invalid")
        self.assertEqual(result.findings[0].line, 2)

    def test_scan_flags_invisible_unicode(self) -> None:
        result = scan_text("safe\u200btext")

        self.assertEqual(result.risk_level, "high")
        self.assertEqual(result.findings[0].finding_type, "unicode_invisible")
        self.assertEqual(result.findings[0].column, 5)

    def test_finding_serializes_to_dict(self) -> None:
        result = scan_text("prefix\n" + ("A" * 120))
        finding = result.findings[0].to_dict()

        self.assertEqual(finding["type"], "dense_base64_like")
        self.assertEqual(finding["line"], 2)


if __name__ == "__main__":
    unittest.main()
