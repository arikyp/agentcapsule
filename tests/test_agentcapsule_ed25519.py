import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agentcapsule.cli import main


HAS_CRYPTOGRAPHY = importlib.util.find_spec("cryptography") is not None


@unittest.skipUnless(HAS_CRYPTOGRAPHY, "cryptography optional signing extra is not installed")
class AgentCapsuleEd25519Tests(unittest.TestCase):
    def test_ed25519_pack_verify_inspect_roundtrip_with_inline_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = root / "publisher.key"
            public_key = root / "publisher.pub"
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("public signed state", encoding="utf-8")

            self.assertEqual(
                _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]),
                0,
            )
            self.assertEqual(private_key.stat().st_mode & 0o777, 0o600)
            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--sign-ed25519-key",
                        str(private_key),
                        "--signature-key-id",
                        "publisher-test",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--json"])
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            verified = json.loads(stdout)
            self.assertEqual(verified["signature_verification"], "ok")

            status, stdout, stderr = _capture_cli(["inspect", str(capsule), "--json"])
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            inspected = json.loads(stdout)
            self.assertEqual(inspected["signature_mode"], "ed25519")
            self.assertEqual(inspected["signature_key_id"], "publisher-test")
            self.assertTrue(inspected["signature_public_key_inline"])
            self.assertEqual(inspected["signature_verification"], "ok")

    def test_ed25519_capsule_without_inline_key_requires_public_key_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = root / "publisher.key"
            public_key = root / "publisher.pub"
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("registry mode state", encoding="utf-8")

            self.assertEqual(
                _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]),
                0,
            )
            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--sign-ed25519-key",
                        str(private_key),
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["verify", str(capsule)])
            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("missing inline Ed25519 public key", stderr)

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--ed25519-public-key", str(public_key)])
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")

    def test_ed25519_rejects_modified_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = root / "publisher.key"
            public_key = root / "publisher.pub"
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("signed state", encoding="utf-8")

            self.assertEqual(
                _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]),
                0,
            )
            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule), "--sign-ed25519-key", str(private_key)]), 0)
            capsule.write_text(
                capsule.read_text(encoding="utf-8").replace("created_by: local", "created_by: other", 1),
                encoding="utf-8",
            )

            status, stdout, stderr = _capture_cli(["verify", str(capsule)])

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature verification failed", stderr)

    def test_ed25519_rejects_wrong_public_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = root / "publisher.key"
            public_key = root / "publisher.pub"
            other_private_key = root / "other.key"
            other_public_key = root / "other.pub"
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("signed state", encoding="utf-8")

            self.assertEqual(
                _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]),
                0,
            )
            self.assertEqual(
                _run_cli(["keys", "generate", "--private-key", str(other_private_key), "--public-key", str(other_public_key)]),
                0,
            )
            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--sign-ed25519-key",
                        str(private_key),
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--ed25519-public-key", str(other_public_key)])

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("public key fingerprint mismatch", stderr)

    def test_ed25519_policy_can_require_public_key_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key = root / "publisher.key"
            public_key = root / "publisher.pub"
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            policy = root / "policy.json"
            source.write_text("signed state", encoding="utf-8")
            policy.write_text(
                json.dumps({"allow_unsigned": False, "required_signature_modes": ["ed25519"]}),
                encoding="utf-8",
            )

            self.assertEqual(
                _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]),
                0,
            )
            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule), "--sign-ed25519-key", str(private_key)]), 0)

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--policy", str(policy)])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")


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
