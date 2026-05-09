import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agentcapsule.cli import main
from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.errors import CapsulePolicyError
from agentcapsule.policy import load_policy, policy_from_mapping
from agentcapsule.registry import describe_codec, known_codecs, list_codecs
from agentcapsule.scanner import scan_text


class AgentCapsulePolicyTests(unittest.TestCase):
    def test_policy_from_json_overrides_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text(
                json.dumps(
                    {
                        "allow_unsigned": False,
                        "allowed_content_types": ["application/octet-stream"],
                        "max_payload_bytes": 7,
                    }
                ),
                encoding="utf-8",
            )

            policy = load_policy(path)

            self.assertFalse(policy.allow_unsigned)
            self.assertEqual(policy.allowed_content_types, frozenset({"application/octet-stream"}))
            self.assertEqual(policy.max_payload_bytes, 7)

    def test_policy_rejects_unknown_fields(self) -> None:
        with self.assertRaisesRegex(CapsulePolicyError, "unknown policy fields"):
            policy_from_mapping({"max_payload_bytez": 1})

    def test_cli_policy_blocks_oversized_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capsule = root / "capsule.txt"
            policy = root / "policy.json"
            capsule.write_text(render_envelope(build_envelope(b"too large")), encoding="utf-8")
            policy.write_text(json.dumps({"max_payload_bytes": 3}), encoding="utf-8")

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertNotEqual(main(["verify", str(capsule), "--policy", str(policy)]), 0)

    def test_policy_rejects_unsigned_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capsule = root / "capsule.txt"
            policy = root / "policy.json"
            capsule.write_text(render_envelope(build_envelope(b"payload")), encoding="utf-8")
            policy.write_text(
                json.dumps({"allow_unsigned": False, "required_signature_modes": ["hmac-sha256"]}),
                encoding="utf-8",
            )

            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertNotEqual(main(["verify", str(capsule), "--policy", str(policy)]), 0)

    def test_scan_applies_policy_to_capsules(self) -> None:
        policy = policy_from_mapping({"max_payload_bytes": 3})
        result = scan_text(render_envelope(build_envelope(b"too large")), policy=policy)

        self.assertEqual(result.capsules_detected, 1)
        self.assertEqual(result.valid_capsules, 0)
        self.assertEqual(result.invalid_capsules, 1)
        self.assertEqual(result.risk_level, "high")

    def test_registry_describes_installed_codecs(self) -> None:
        self.assertEqual(known_codecs(), ("base64", "lmcodec-fixed", "lmcodec-ngram-v2"))
        self.assertEqual([codec.name for codec in list_codecs()], ["base64", "lmcodec-fixed", "lmcodec-ngram-v2"])
        self.assertEqual(describe_codec("base64").purpose, "stable interoperability baseline")
        self.assertEqual(describe_codec("lmcodec-ngram-v2").purpose, "self-contained LMCodec n-gram capsule backend")
        self.assertIsNone(describe_codec("missing"))


if __name__ == "__main__":
    unittest.main()
