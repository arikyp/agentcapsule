import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agentcapsule.cli import main
from agentcapsule.envelope import build_envelope, render_envelope


class AgentCapsuleAuditTests(unittest.TestCase):
    def test_inspect_audit_allows_valid_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule = Path(tmp) / "capsule.txt"
            capsule.write_text(render_envelope(build_envelope(b"payload")), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["inspect", str(capsule), "--audit-json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            event = json.loads(stdout)
            self.assertEqual(event["event_type"], "agent_capsule_audit")
            self.assertEqual(event["operation"], "inspect")
            self.assertEqual(event["disposition"], "allow")
            self.assertEqual(event["result"]["verification_status"], "ok")

    def test_scan_audit_reviews_dense_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "message.txt"
            text_file.write_text("prefix\n" + ("A" * 120), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["scan", str(text_file), "--audit-json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            event = json.loads(stdout)
            self.assertEqual(event["operation"], "scan")
            self.assertEqual(event["disposition"], "review")
            self.assertEqual(event["result"]["risk_level"], "medium")

    def test_verify_audit_blocks_invalid_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule = Path(tmp) / "bad.txt"
            capsule.write_text("not a capsule", encoding="utf-8")

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--audit-json"])

            self.assertEqual(status, 2)
            self.assertEqual(stderr, "")
            event = json.loads(stdout)
            self.assertEqual(event["operation"], "verify")
            self.assertEqual(event["disposition"], "block")
            self.assertIn("missing capsule begin marker", event["reasons"][0])

    def test_unpack_audit_includes_files_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            out = root / "decoded"
            source.write_text("exact state", encoding="utf-8")
            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule)]), 0)

            status, stdout, stderr = _capture_cli(["unpack", str(capsule), "--out", str(out), "--audit-json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            event = json.loads(stdout)
            self.assertEqual(event["operation"], "unpack")
            self.assertEqual(event["disposition"], "allow")
            self.assertEqual(len(event["result"]["files_written"]), 1)


def _run_cli(args: list[str]) -> int:
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return main(args)


def _capture_cli(args: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = main(args)
    return status, stdout.getvalue(), stderr.getvalue()


if __name__ == "__main__":
    unittest.main()
