import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.receiver import ingest_messages


class AgentCapsuleReceiverTests(unittest.TestCase):
    def test_ingest_messages_handles_inline_reference_and_malformed_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "sandbox"

            inline_capsule = render_envelope(build_envelope(b"inline payload", filename="inline.txt"))
            reference_capsule = render_envelope(build_envelope(b"reference payload", filename="reference.txt"))
            reference_sha = hashlib.sha256(reference_capsule.encode("utf-8")).hexdigest()
            transcript = "\n".join(
                [
                    "sender: capsule follows",
                    inline_capsule,
                    json.dumps(
                        {
                            "reference_type": "agent_capsule_reference",
                            "schema_version": 1,
                            "capsule_uri": "https://example.test/capsules/ref-1.txt",
                            "capsule_sha256": reference_sha,
                        }
                    ),
                    "-----BEGIN AGENT CAPSULE-----",
                    "truncated",
                ]
            )

            def _mock_fetch(uri, *, expected_sha256=None, save_path=None, resumable=False):
                self.assertEqual(uri, "https://example.test/capsules/ref-1.txt")
                self.assertEqual(expected_sha256, reference_sha)
                data = reference_capsule.encode("utf-8")
                if save_path:
                    save_path.write_bytes(data)
                return data

            with patch("agentcapsule.receiver.fetch_capsule", side_effect=_mock_fetch):
                result = ingest_messages(
                    messages=[{"content": transcript}],
                    out_dir=out,
                )

            self.assertEqual(result.malformed_blocks, 1)
            self.assertEqual(len(result.inline_capsules), 1)
            self.assertEqual(len(result.references), 1)
            self.assertEqual(result.references[0]["status"], "unpacked")

            unpacked_names = sorted(Path(path).name for path in result.unpacked_files)
            self.assertEqual(unpacked_names, ["inline.txt", "reference.txt"])


if __name__ == "__main__":
    unittest.main()
