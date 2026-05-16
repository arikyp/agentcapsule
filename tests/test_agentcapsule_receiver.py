import base64
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agentcapsule.envelope import build_envelope, parse_envelope, render_envelope
from agentcapsule.errors import CapsuleVerificationError
from agentcapsule.manifest import BUNDLE_CONTENT_TYPE, BUNDLE_FORMAT
from agentcapsule.receiver import ingest_messages, verify_capsule


class AgentCapsuleReceiverTests(unittest.TestCase):
    def _require_cryptography(self) -> None:
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")

    def test_ingest_messages_handles_inline_reference_and_malformed_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "sandbox"

            inline_capsule = render_envelope(build_envelope(b"inline payload", filename="inline.txt"))
            reference_capsule = render_envelope(build_envelope(b"reference payload", filename="reference.txt"))
            reference_sha = hashlib.sha256(reference_capsule.encode("utf-8")).hexdigest()
            reference_payload_sha = parse_envelope(reference_capsule).payload_sha256
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
                            "payload_sha256": reference_payload_sha,
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
            self.assertTrue(result.has_failures)
            self.assertIsNotNone(result.scan_report)
            self.assertTrue(result.inline_capsules[0]["accepted"])
            self.assertEqual(result.inline_capsules[0]["reason_code"], None)
            self.assertTrue(result.references[0]["accepted"])
            self.assertEqual(result.references[0]["fetched"], True)
            self.assertEqual(result.scan_report["disposition"], "block")

            payload = result.to_dict()
            self.assertEqual(payload["report_type"], "agent_capsule_ingest_report")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["disposition"], "block")
            self.assertEqual(payload["accepted_capsules_count"], 2)
            self.assertEqual(payload["rejected_capsules_count"], 0)
            self.assertEqual(payload["fetched_references_count"], 1)
            self.assertEqual(payload["unpacked_files_count"], 2)
            self.assertEqual(payload["rejected_reasons_by_type"], {"MALFORMED_CAPSULE_BLOCK": 1})
            self.assertIn("max_payload_bytes", payload["effective_policy"])

            unpacked_names = sorted(Path(path).name for path in result.unpacked_files)
            self.assertEqual(unpacked_names, ["inline.txt", "reference.txt"])

    def test_ingest_messages_detects_reference_payload_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "sandbox"

            reference_capsule = render_envelope(build_envelope(b"reference payload", filename="reference.txt"))
            reference_sha = hashlib.sha256(reference_capsule.encode("utf-8")).hexdigest()
            transcript = "\n".join(
                [
                    json.dumps(
                        {
                            "reference_type": "agent_capsule_reference",
                            "schema_version": 1,
                            "capsule_uri": "https://example.test/capsules/ref-1.txt",
                            "capsule_sha256": reference_sha,
                            "payload_sha256": "0" * 64,
                        }
                    ),
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
                result = ingest_messages(messages=[{"content": transcript}], out_dir=out)

            self.assertEqual(len(result.references), 1)
            self.assertEqual(result.references[0]["status"], "failed")
            self.assertEqual(result.references[0]["accepted"], False)
            self.assertEqual(result.references[0]["stage"], "verify")
            self.assertEqual(result.references[0]["reason_code"], "REFERENCE_PAYLOAD_HASH_MISMATCH")
            self.assertIn("payload_sha256", result.references[0]["error"])
            self.assertTrue(result.has_failures)
            self.assertEqual(result.to_dict()["rejected_reasons_by_type"], {"REFERENCE_PAYLOAD_HASH_MISMATCH": 1})

    def test_verify_rejects_manifest_payload_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capsule = root / "capsule.txt"
            payload = b"actual payload"
            bundle = {
                "format": BUNDLE_FORMAT,
                "files": [
                    {
                        "path": "actual.txt",
                        "size": len(payload),
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "content_base64": base64.b64encode(payload).decode("ascii"),
                    }
                ],
            }
            envelope = build_envelope(
                json.dumps(bundle, sort_keys=True, separators=(",", ":")).encode("utf-8"),
                content_type=BUNDLE_CONTENT_TYPE,
                manifest_files=[
                    {
                        "path": "claimed.txt",
                        "sha256": hashlib.sha256(b"claimed").hexdigest(),
                        "bytes": len(b"claimed"),
                    }
                ],
            )
            capsule.write_text(render_envelope(envelope), encoding="utf-8")

            with self.assertRaisesRegex(CapsuleVerificationError, "capsule manifest files do not match bundle payload files"):
                verify_capsule(capsule)

    def test_ingest_with_encrypted_capsule_and_decryption_key_keeps_scan_consistent(self) -> None:
        self._require_cryptography()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / "sandbox"
            key = b"k" * 32
            encoded_key = base64.b64encode(key).decode("ascii")
            capsule_text = render_envelope(
                build_envelope(
                    b"secret payload",
                    filename="secret.txt",
                    encryption_key=key,
                )
            )
            with patch.dict("os.environ", {"CAPSULE_KEY": encoded_key}, clear=False):
                result = ingest_messages(
                    messages=[{"content": capsule_text}],
                    out_dir=out,
                    encryption_key_env="CAPSULE_KEY",
                )

            payload = result.to_dict()
            self.assertEqual(payload["disposition"], "allow")
            self.assertEqual(payload["scan_report"]["disposition"], "allow")
            self.assertEqual(payload["scan_report"]["invalid_capsules"], 0)
            self.assertEqual(result.inline_capsules[0]["status"], "unpacked")


if __name__ == "__main__":
    unittest.main()
