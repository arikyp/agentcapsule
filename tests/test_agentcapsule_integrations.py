import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentcapsule.cli import main
from agentcapsule.errors import CapsuleVerificationError
from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.integrations import AutoIngest


class AgentCapsuleIntegrationsTests(unittest.TestCase):
    def test_autoingest_scan_history_finds_inline_capsule(self) -> None:
        messages = ["header", "handoff\n" + render_envelope(build_envelope(b"payload"))]
        envelopes = AutoIngest.scan_history(messages)

        self.assertEqual(len(envelopes), 1)
        self.assertEqual(envelopes[0].payload_sha256, build_envelope(b"payload").payload_sha256)

    def test_autoingest_fetch_from_history_fetches_reference_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload_file = root / "payload.txt"
            payload_file.write_text("exact state", encoding="utf-8")
            capsule_file = root / "capsule.txt"
            self.assertEqual(main(["pack", str(payload_file), "--out", str(capsule_file)]), 0)

            reference_stdout = _capture_stdout(
                ["reference", str(capsule_file), "--uri", capsule_file.resolve().as_uri(), "--json"]
            )
            descriptor = json.loads(reference_stdout)
            messages = [f"handoff\n{json.dumps(descriptor)}"]

            with patch.dict(os.environ, {"AGENTCAPSULE_ALLOW_FILE_URI": "1"}, clear=False):
                fetched = AutoIngest.fetch_from_history(messages)
            self.assertEqual(len(fetched), 1)
            self.assertEqual(fetched[0]["capsule_uri"], capsule_file.resolve().as_uri())
            self.assertEqual(fetched[0]["payload_bytes"], len(b"exact state"))

    def test_autoingest_rejects_file_uri_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload_file = root / "payload.txt"
            payload_file.write_text("exact state", encoding="utf-8")
            capsule_file = root / "capsule.txt"
            self.assertEqual(main(["pack", str(payload_file), "--out", str(capsule_file)]), 0)
            reference_stdout = _capture_stdout(
                ["reference", str(capsule_file), "--uri", capsule_file.resolve().as_uri(), "--json"]
            )
            descriptor = json.loads(reference_stdout)
            messages = [f"handoff\n{json.dumps(descriptor)}"]
            with self.assertRaisesRegex(CapsuleVerificationError, "unsupported URI scheme: file"):
                AutoIngest.fetch_from_history(messages)


def _capture_stdout(argv: list[str]) -> str:
    from contextlib import redirect_stderr, redirect_stdout
    from io import StringIO

    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = main(argv)
    if status != 0:
        raise AssertionError(stderr.getvalue().strip())
    return stdout.getvalue().strip()


if __name__ == "__main__":
    unittest.main()
