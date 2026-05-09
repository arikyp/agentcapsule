import unittest

from agentcapsule.envelope import build_envelope, parse_envelope, render_envelope, verify_envelope
from agentcapsule.errors import CapsuleParseError, CapsuleVerificationError


class AgentCapsuleEnvelopeTests(unittest.TestCase):
    def test_parse_valid_capsule(self) -> None:
        envelope = build_envelope(b"hello capsule", codec="base64", created_at="2026-05-09T00:00:00Z")
        text = render_envelope(envelope)
        parsed = parse_envelope(text.replace("\n", "\r\n"))

        self.assertEqual(parsed.headers["capsule_version"], "0.1")
        self.assertEqual(parsed.codec, "base64")
        self.assertEqual(verify_envelope(parsed), b"hello capsule")

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


if __name__ == "__main__":
    unittest.main()
