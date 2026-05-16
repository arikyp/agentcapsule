import importlib.util
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agentcapsule.cli import main
from agentcapsule.envelope import build_envelope, render_envelope
from agentcapsule.signing import encode_key_bytes, load_private_key_file, sign_envelope_ed25519
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

    def test_backdated_capsule_cannot_bypass_expired_registry_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            registry = _write_registry(
                root,
                public_key,
                key_id="publisher-prod",
                publisher="Example Publisher",
                expires_at="2020-01-01T00:00:00Z",
            )
            policy = _write_policy(root, require_registry=True)
            capsule = root / "capsule.txt"
            envelope = build_envelope(
                b"trusted registry state",
                created_at="2019-01-01T00:00:00Z",
            )
            signed = sign_envelope_ed25519(
                envelope,
                private_key_bytes=load_private_key_file(private_key),
                key_id="publisher-prod",
                inline_public_key=False,
            )
            capsule.write_text(render_envelope(signed), encoding="utf-8")

            status, stdout, stderr = _capture_cli(
                ["verify", str(capsule), "--policy", str(policy), "--signature-registry", str(registry)]
            )

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature key is not trusted by local registry", stderr)

    def test_verify_accepts_multiple_signature_registry_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            left_registry = _write_registry(root, public_key, key_id="other-publisher")
            right_registry = _write_registry(root, public_key, key_id="publisher-prod", filename="registry-right.json")
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("multi-registry state", encoding="utf-8")

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
                    str(left_registry),
                    "--signature-registry",
                    str(right_registry),
                    "--json",
                ]
            )

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["signature_trust"]["status"], "trusted")

    def test_verify_applies_revoked_wins_across_merged_registries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            private_key, public_key = _generate_keys(root)
            trusted_registry = _write_registry(root, public_key, key_id="publisher-prod", filename="trusted-registry.json")
            revoked_registry = _write_registry(
                root,
                public_key,
                key_id="publisher-prod",
                status="revoked",
                filename="revoked-registry.json",
            )
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("revoked merge state", encoding="utf-8")

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
                    str(trusted_registry),
                    "--signature-registry",
                    str(revoked_registry),
                ]
            )

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature key is revoked by local registry", stderr)

    def test_trust_import_snapshot_writes_local_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_private, root_public = _generate_keys(root, prefix="root")
            publisher_private, publisher_public = _generate_keys(root, prefix="publisher")
            snapshot_path = root / "snapshot.json"
            local_registry = root / "local-registry.json"
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("snapshot import state", encoding="utf-8")

            entry = registry_entry_from_public_key_file(
                key_id="publisher-prod",
                public_key_path=publisher_public,
                publisher="Example Publisher",
                status="trusted",
            )
            snapshot_payload = {
                "registry_version": 1,
                "issuer": "example-agent-trust",
                "sequence": 42,
                "created_at": "2026-05-10T00:00:00Z",
                "expires_at": "2030-05-10T00:00:00Z",
                "keys": [entry],
            }
            snapshot_path.write_text(json.dumps(_signed_snapshot(snapshot_payload, root_private, key_id="root-2026")), encoding="utf-8")

            status, stdout, stderr = _capture_cli(
                [
                    "trust",
                    "import-snapshot",
                    "--snapshot",
                    str(snapshot_path),
                    "--trusted-root-key",
                    str(root_public),
                    "--issuer",
                    "example-agent-trust",
                    "--out",
                    str(local_registry),
                    "--json",
                ]
            )
            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["operation"], "trust_snapshot_import")
            self.assertEqual(payload["issuer"], "example-agent-trust")
            self.assertTrue(local_registry.exists())

            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--sign-ed25519-key",
                        str(publisher_private),
                        "--signature-key-id",
                        "publisher-prod",
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )
            verify_status, verify_stdout, verify_stderr = _capture_cli(
                ["verify", str(capsule), "--policy", str(policy), "--signature-registry", str(local_registry), "--json"]
            )
            self.assertEqual(verify_status, 0)
            self.assertEqual(verify_stderr, "")
            verify_payload = json.loads(verify_stdout)
            self.assertEqual(verify_payload["signature_trust"]["status"], "trusted")

    def test_trust_sync_snapshot_fetches_and_writes_local_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_private, root_public = _generate_keys(root, prefix="root")
            publisher_private, publisher_public = _generate_keys(root, prefix="publisher")
            local_registry = root / "synced-registry.json"
            policy = _write_policy(root, require_registry=True)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("snapshot sync state", encoding="utf-8")

            entry = registry_entry_from_public_key_file(
                key_id="publisher-sync",
                public_key_path=publisher_public,
                publisher="Example Publisher",
                status="trusted",
            )
            snapshot_payload = {
                "registry_version": 1,
                "issuer": "sync-issuer",
                "sequence": 7,
                "created_at": "2026-05-10T00:00:00Z",
                "expires_at": "2030-05-10T00:00:00Z",
                "keys": [entry],
            }
            snapshot_bytes = json.dumps(_signed_snapshot(snapshot_payload, root_private, key_id="root-2026")).encode("utf-8")

            with patch("agentcapsule.fetcher.fetch_capsule", return_value=snapshot_bytes):
                status, stdout, stderr = _capture_cli(
                    [
                        "trust",
                        "sync",
                        "--uri",
                        "https://trust.example/snapshot.json",
                        "--trusted-root-key",
                        str(root_public),
                        "--issuer",
                        "sync-issuer",
                        "--out",
                        str(local_registry),
                        "--json",
                    ]
                )

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["operation"], "trust_snapshot_sync")
            self.assertEqual(payload["issuer"], "sync-issuer")
            self.assertTrue(local_registry.exists())

            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--sign-ed25519-key",
                        str(publisher_private),
                        "--signature-key-id",
                        "publisher-sync",
                        "--no-inline-public-key",
                    ]
                ),
                0,
            )
            verify_status, verify_stdout, verify_stderr = _capture_cli(
                ["verify", str(capsule), "--policy", str(policy), "--signature-registry", str(local_registry), "--json"]
            )
            self.assertEqual(verify_status, 0)
            self.assertEqual(verify_stderr, "")
            verify_payload = json.loads(verify_stdout)
            self.assertEqual(verify_payload["signature_trust"]["status"], "trusted")

    def test_trust_sync_rejects_snapshot_with_public_key_path_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root_private, root_public = _generate_keys(root, prefix="root")
            _publisher_private, publisher_public = _generate_keys(root, prefix="publisher")
            local_registry = root / "synced-registry.json"

            entry = {
                "key_id": "publisher-sync",
                "fingerprint": "0" * 64,
                "public_key_path": publisher_public.name,
                "status": "trusted",
            }
            snapshot_payload = {
                "registry_version": 1,
                "issuer": "sync-issuer",
                "sequence": 8,
                "created_at": "2026-05-10T00:00:00Z",
                "expires_at": "2030-05-10T00:00:00Z",
                "keys": [entry],
            }
            snapshot_bytes = json.dumps(_signed_snapshot(snapshot_payload, root_private, key_id="root-2026")).encode("utf-8")

            with patch("agentcapsule.fetcher.fetch_capsule", return_value=snapshot_bytes):
                status, stdout, stderr = _capture_cli(
                    [
                        "trust",
                        "sync",
                        "--uri",
                        "https://trust.example/snapshot.json",
                        "--trusted-root-key",
                        str(root_public),
                        "--issuer",
                        "sync-issuer",
                        "--out",
                        str(local_registry),
                    ]
                )

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("public_key_path is not allowed", stderr)


def _generate_keys(root: Path, *, prefix: str = "publisher") -> tuple[Path, Path]:
    private_key = root / f"{prefix}.key"
    public_key = root / f"{prefix}.pub"
    assert _run_cli(["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key)]) == 0
    return private_key, public_key


def _write_registry(
    root: Path,
    public_key: Path,
    *,
    key_id: str,
    filename: str = "registry.json",
    publisher: str | None = None,
    status: str = "trusted",
    expires_at: str | None = None,
) -> Path:
    registry = root / filename
    entry = registry_entry_from_public_key_file(
        key_id=key_id,
        public_key_path=public_key,
        publisher=publisher,
        status=status,
    )
    if expires_at:
        entry["expires_at"] = expires_at
    registry.write_text(
        json.dumps(
            {
                "keys": [entry]
            }
        ),
        encoding="utf-8",
    )
    return registry


def _signed_snapshot(payload: dict[str, object], private_key_path: Path, *, key_id: str) -> dict[str, object]:
    from cryptography.hazmat.primitives.asymmetric import ed25519

    signing_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    private_key = ed25519.Ed25519PrivateKey.from_private_bytes(load_private_key_file(private_key_path))
    signature = encode_key_bytes(private_key.sign(signing_payload))
    signed = dict(payload)
    signed["signature"] = {
        "mode": "ed25519",
        "key_id": key_id,
        "signature": signature,
    }
    return signed


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
