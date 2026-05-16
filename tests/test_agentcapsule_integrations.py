import json
import tempfile
import unittest
from pathlib import Path

from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.integrations import (
    FRAMEWORK_REPORT_TYPE,
    FRAMEWORK_SCHEMA_VERSION,
    FrameworkIngestResult,
    ingest_for_framework,
)
from agentcapsule.receiver import ingest_messages


class AgentCapsuleIntegrationsTests(unittest.TestCase):
    def test_ingest_for_framework_returns_stable_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "sandbox"
            message = render_envelope(build_envelope(b"payload", filename="payload.txt"))

            result = ingest_for_framework(messages=message, out_dir=out_dir)
            payload = result.to_dict()

            self.assertEqual(result.report_type, FRAMEWORK_REPORT_TYPE)
            self.assertEqual(result.schema_version, FRAMEWORK_SCHEMA_VERSION)
            self.assertEqual(payload["report_type"], FRAMEWORK_REPORT_TYPE)
            self.assertEqual(payload["schema_version"], FRAMEWORK_SCHEMA_VERSION)
            self.assertEqual(
                set(payload),
                {
                    "report_type",
                    "schema_version",
                    "disposition",
                    "accepted_capsules_count",
                    "rejected_capsules_count",
                    "rejected_reasons_by_type",
                    "unpacked_files_count",
                    "unpacked_files",
                    "inline_capsules",
                    "references",
                    "malformed_blocks",
                    "effective_policy",
                    "scan_report",
                },
            )
            self.assertEqual(payload["accepted_capsules_count"], 1)
            self.assertEqual(payload["rejected_capsules_count"], 0)
            self.assertEqual(payload["unpacked_files_count"], 1)

    def test_ingest_for_framework_matches_receiver_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_framework = root / "framework"
            out_receiver = root / "receiver"
            inline_capsule = render_envelope(build_envelope(b"inline payload", filename="inline.txt"))
            transcript = "\n".join(
                [
                    "sender: handoff",
                    inline_capsule,
                    "-----BEGIN AGENT CAPSULE-----",
                    "truncated",
                ]
            )

            framework = ingest_for_framework(messages=[{"content": transcript}], out_dir=out_framework)
            receiver = ingest_messages(messages=[{"content": transcript}], out_dir=out_receiver).to_dict()

            self.assertEqual(framework.disposition, receiver["disposition"])
            self.assertEqual(framework.accepted_capsules_count, receiver["accepted_capsules_count"])
            self.assertEqual(framework.rejected_capsules_count, receiver["rejected_capsules_count"])
            self.assertEqual(framework.rejected_reasons_by_type, receiver["rejected_reasons_by_type"])
            self.assertEqual(framework.unpacked_files_count, receiver["unpacked_files_count"])
            self.assertEqual(framework.malformed_blocks, receiver["malformed_blocks"])
            self.assertEqual(framework.blocked, receiver["disposition"] == "block")

    def test_framework_result_helpers(self) -> None:
        result = FrameworkIngestResult(
            report_type=FRAMEWORK_REPORT_TYPE,
            schema_version=FRAMEWORK_SCHEMA_VERSION,
            disposition="review",
            accepted_capsules_count=1,
            rejected_capsules_count=0,
            rejected_reasons_by_type={},
            unpacked_files_count=1,
            unpacked_files=["/tmp/payload.txt"],
            inline_capsules=[],
            references=[],
            malformed_blocks=0,
            effective_policy={},
            scan_report={"risk_level": "medium"},
        )

        self.assertFalse(result.blocked)
        self.assertTrue(result.review_required)
        json.dumps(result.to_dict())


if __name__ == "__main__":
    unittest.main()
