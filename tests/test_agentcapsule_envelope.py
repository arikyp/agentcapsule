import hashlib
import json
import unittest

from agentcapsule.envelope import build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.errors import CapsuleParseError, CapsuleVerificationError


class AgentCapsuleEnvelopeTests(unittest.TestCase):
    def _require_cryptography(self) -> None:
        try:
            import cryptography  # noqa: F401
        except ImportError:
            self.skipTest("cryptography not installed")

    def test_parse_valid_capsule(self) -> None:
        envelope = build_envelope(b"hello capsule", codec="base64", created_at="2026-05-09T00:00:00Z")
        text = render_envelope(envelope)
        parsed = parse_envelope(text.replace("\n", "\r\n"))

        self.assertEqual(parsed.headers["capsule_version"], "0.1")
        self.assertEqual(parsed.codec, "base64")
        self.assertEqual(verify_envelope(parsed), b"hello capsule")

    def test_builds_capsule_manifest_header(self) -> None:
        envelope = build_envelope(
            b"diff",
            filename="patch.diff",
            created_by="agent-a",
            task_id="abc123",
            requested_capabilities=["read_files", "run_tests"],
            policy_hints={"network_egress": False, "sandbox_required": True},
            created_at="2026-05-09T00:00:00Z",
        )
        parsed = parse_envelope(render_envelope(envelope))

        manifest = parsed.capsule_manifest

        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(manifest["capsule_type"], "agent_handoff")
        self.assertEqual(manifest["created_by"], "agent-a")
        self.assertEqual(manifest["task_id"], "abc123")
        self.assertEqual(manifest["delivery"], {"mode": "inline"})
        self.assertEqual(manifest["requested_capabilities"], ["read_files", "run_tests"])
        self.assertEqual(manifest["policy_hints"], {"network_egress": False, "sandbox_required": True})
        self.assertEqual(
            manifest["files"],
            [
                {
                    "path": "patch.diff",
                    "sha256": hashlib.sha256(b"diff").hexdigest(),
                    "bytes": 4,
                }
            ],
        )

    def test_rejects_malformed_capsule_manifest_header(self) -> None:
        envelope = build_envelope(b"payload")
        bad_manifest = json.dumps({"capsule_type": "agent_handoff"})
        text = render_envelope(envelope).replace(envelope.headers["capsule_manifest"], bad_manifest)

        with self.assertRaisesRegex(CapsuleParseError, "missing capsule manifest fields"):
            parse_envelope(text)

    def test_builds_reference_delivery_metadata(self) -> None:
        envelope = build_envelope(
            b"payload",
            delivery_mode="reference",
            delivery_uri="https://example.test/capsules/abc.txt",
        )

        manifest = envelope.capsule_manifest

        self.assertIsNotNone(manifest)
        assert manifest is not None
        self.assertEqual(
            manifest["delivery"],
            {"mode": "reference", "uri": "https://example.test/capsules/abc.txt"},
        )

    def test_rejects_reference_delivery_without_uri(self) -> None:
        with self.assertRaisesRegex(CapsuleParseError, "reference delivery requires a uri"):
            build_envelope(b"payload", delivery_mode="reference")

    def test_reject_malformed_capsule(self) -> None:
        envelope = build_envelope(b"payload")
        text = render_envelope(envelope).replace("codec: base64\n", "")

        with self.assertRaisesRegex(CapsuleParseError, "missing required"):
            parse_envelope(text)

    def test_sha_mismatch_detected(self) -> None:
        envelope = build_envelope(b"payload")
        text = render_envelope(envelope).replace(envelope.payload_sha256, "0" * 64)
        parsed = parse_envelope(text)

        with self.assertRaisesRegex(CapsuleVerificationError, "SHA256 mismatch"):
            verify_envelope(parsed)

    def test_encrypted_capsule_binds_metadata_with_aad(self) -> None:
        self._require_cryptography()
        key = b"k" * 32
        envelope = build_envelope(
            b"payload",
            encryption_key=key,
            filename="payload.bin",
            created_by="agent-a",
            extra_headers={"lmcodec_model_type": "ngram-v1"},
        )
        parsed = parse_envelope(render_envelope(envelope))
        self.assertEqual(verify_envelope(parsed, encryption_key=key), b"payload")

        tampered_text = render_envelope(envelope).replace("created_by: agent-a", "created_by: agent-b", 1)
        tampered = parse_envelope(tampered_text)
        with self.assertRaisesRegex(CapsuleVerificationError, "decryption failed"):
            verify_envelope(tampered, encryption_key=key)

    def test_encrypted_capsule_binds_extra_headers_with_aad(self) -> None:
        self._require_cryptography()
        key = b"k" * 32
        envelope = build_envelope(
            b"payload",
            encryption_key=key,
            extra_headers={"lmcodec_model_type": "ngram-v1"},
        )
        tampered_text = render_envelope(envelope).replace("lmcodec_model_type: ngram-v1", "lmcodec_model_type: ngram-v2", 1)
        tampered = parse_envelope(tampered_text)
        with self.assertRaisesRegex(CapsuleVerificationError, "decryption failed"):
            verify_envelope(tampered, encryption_key=key)


if __name__ == "__main__":
    unittest.main()
