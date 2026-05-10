import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

from agentcapsule.cli import main
from agentcapsule.trust import registry_entry_from_public_key_file


HAS_CRYPTOGRAPHY = importlib.util.find_spec("cryptography") is not None


@unittest.skipUnless(HAS_CRYPTOGRAPHY, "cryptography optional signing extra is not installed")
class AgentCapsuleRegistryTests(unittest.TestCase):
    def test_verify_trusts_registry_key_without_inline_public_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            registry = _write_registry(root, public_key, key_id="publisher-prod", publisher="Example Publisher")
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("trusted registry state", encoding="utf-8")

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
                        "publisher-prod",
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(
                ["verify", str(capsule), "--policy", str(policy), "--signature-registry", str(registry), "--json"]
            )

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["signature_trust"]["status"], "trusted")
            self.assertEqual(payload["signature_trust"]["publisher"], "Example Publisher")

    def test_require_registry_rejects_inline_key_without_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, _ = _generate_keys(root)
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("inline state", encoding="utf-8")

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
                        "publisher-prod",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--policy", str(policy)])

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("inline public keys are not allowed", stderr)

    def test_revoked_registry_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            registry = _write_registry(root, public_key, key_id="publisher-prod", status="revoked")
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("revoked state", encoding="utf-8")

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
                        "publisher-prod",
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(
                ["verify", str(capsule), "--policy", str(policy), "--signature-registry", str(registry)]
            )

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature key is revoked by local registry", stderr)

    def test_policy_trusted_key_id_rejects_other_key_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            registry = _write_registry(root, public_key, key_id="publisher-dev")
            policy = _write_policy(root, require_registry=True, trusted_ids=["publisher-prod"])
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("wrong key id state", encoding="utf-8")

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
                        "publisher-dev",
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(
                ["verify", str(capsule), "--policy", str(policy), "--signature-registry", str(registry)]
            )

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature key id is not trusted by policy", stderr)

    def test_scan_flags_untrusted_inline_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, _ = _generate_keys(root)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("inline state", encoding="utf-8")
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
                        "publisher-prod",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["scan", str(capsule), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertIn("signature_untrusted", [finding["type"] for finding in payload["findings"]])

    def test_keys_registry_entry_outputs_registry_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _, public_key = _generate_keys(root)

            status, stdout, stderr = _capture_cli(
                [
                    "keys",
                    "registry-entry",
                    "--key-id",
                    "publisher-prod",
                    "--public-key",
                    str(public_key),
                    "--publisher",
                    "Example Publisher",
                ]
            )

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["keys"][0]["key_id"], "publisher-prod")
            self.assertEqual(payload["keys"][0]["publisher"], "Example Publisher")

    def test_verify_audit_allows_trusted_registry_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            registry = _write_registry(root, public_key, key_id="publisher-prod", publisher="Example Publisher")
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("trusted registry state", encoding="utf-8")
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
                        "publisher-prod",
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(
                [
                    "verify",
                    str(capsule),
                    "--policy",
                    str(policy),
                    "--signature-registry",
                    str(registry),
                    "--audit-json",
                ]
            )

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            event = json.loads(stdout)
            self.assertEqual(event["operation"], "verify")
            self.assertEqual(event["disposition"], "allow")
            self.assertEqual(event["result"]["signature_trust"]["status"], "trusted")


def _generate_keys(root: Path) -> tuple[Path, Path]:
    private_key = root / "publisher.key"
    public_key = root / "publisher.pub"
    assert _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]) == 0
    return private_key, public_key


def _write_registry(
    root: Path,
    public_key: Path,
    *,
    key_id: str,
    publisher: str | None = None,
    status: str = "trusted",
) -> Path:
    registry = root / "registry.json"
    registry.write_text(
        json.dumps(
            {
                "keys": [
                    registry_entry_from_public_key_file(
                        key_id=key_id,
                        public_key_path=public_key,
                        publisher=publisher,
                        status=status,
                    )
                ]
            }
        ),
        encoding="utf-8",
    )
    return registry


def _write_policy(root: Path, *, require_registry: bool, trusted_ids: list[str] | None = None) -> Path:
    policy = root / "policy.json"
    payload: dict[str, object] = {
        "allow_unsigned": False,
        "required_signature_modes": ["ed25519"],
        "require_signature_registry": require_registry,
        "allow_inline_public_keys": not require_registry,
    }
    if trusted_ids is not None:
        payload["trusted_signature_key_ids"] = trusted_ids
    policy.write_text(json.dumps(payload), encoding="utf-8")
    return policy


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
