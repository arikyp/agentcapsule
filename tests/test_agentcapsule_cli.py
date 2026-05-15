import hashlib
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from agentcapsule.cli import main
from agentcapsule.envelope import build_envelope, render_envelope


class AgentCapsuleCliTests(unittest.TestCase):
    def test_base64_pack_verify_unpack_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            out = root / "decoded"
            source.write_text("exact state", encoding="utf-8")

            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule)]), 0)
            self.assertEqual(_run_cli(["verify", str(capsule)]), 0)
            self.assertEqual(_run_cli(["unpack", str(capsule), "--out", str(out)]), 0)

            self.assertEqual((out / "payload.txt").read_text(encoding="utf-8"), "exact state")

    def test_lmcodec_fixed_pack_verify_unpack_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.bin"
            capsule = root / "capsule.txt"
            out = root / "decoded"
            source.write_bytes(b"abc123")

            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule), "--codec", "lmcodec-fixed"]), 0)
            self.assertEqual(_run_cli(["verify", str(capsule)]), 0)
            self.assertEqual(_run_cli(["unpack", str(capsule), "--out", str(out)]), 0)

            self.assertEqual((out / "payload.bin").read_bytes(), b"abc123")

    def test_lmcodec_ngram_v2_pack_verify_unpack_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.bin"
            capsule = root / "capsule.txt"
            out = root / "decoded"
            source.write_bytes(b"ngram-v2")

            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--codec",
                        "lmcodec-ngram-v2",
                        "--model",
                        "tests/fixtures/ngram_model_v1.json",
                    ]
                ),
                0,
            )
            self.assertEqual(_run_cli(["verify", str(capsule)]), 0)
            self.assertEqual(_run_cli(["unpack", str(capsule), "--out", str(out)]), 0)

            self.assertEqual((out / "payload.bin").read_bytes(), b"ngram-v2")

    def test_lmcodec_ngram_v2_pack_requires_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.bin"
            capsule = root / "capsule.txt"
            source.write_bytes(b"ngram-v2")

            status, stdout, stderr = _capture_cli(
                ["pack", str(source), "--out", str(capsule), "--codec", "lmcodec-ngram-v2"]
            )

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("requires --model", stderr)

    def test_signed_capsule_verifies_with_correct_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CAPSULE_HMAC_KEY": "secret"}, clear=False):
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("signed state", encoding="utf-8")

            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--sign-key-env",
                        "CAPSULE_HMAC_KEY",
                        "--signature-key-id",
                        "test-key",
                    ]
                ),
                0,
            )
            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--key-env", "CAPSULE_HMAC_KEY", "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["signature_verification"], "ok")

    def test_signed_capsule_rejects_wrong_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("signed state", encoding="utf-8")
            with patch.dict(os.environ, {"CAPSULE_HMAC_KEY": "secret"}, clear=False):
                self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule), "--sign-key-env", "CAPSULE_HMAC_KEY"]), 0)
            with patch.dict(os.environ, {"CAPSULE_HMAC_KEY": "wrong"}, clear=False):
                status, stdout, stderr = _capture_cli(["verify", str(capsule), "--key-env", "CAPSULE_HMAC_KEY"])

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature verification failed", stderr)

    def test_signed_capsule_rejects_modified_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CAPSULE_HMAC_KEY": "secret"}, clear=False):
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("signed state", encoding="utf-8")
            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule), "--sign-key-env", "CAPSULE_HMAC_KEY"]), 0)
            text = capsule.read_text(encoding="utf-8").replace("created_by: local", "created_by: other", 1)
            capsule.write_text(text, encoding="utf-8")

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--key-env", "CAPSULE_HMAC_KEY"])

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature verification failed", stderr)

    def test_signed_capsule_rejects_modified_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"CAPSULE_HMAC_KEY": "secret"}, clear=False):
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("signed state", encoding="utf-8")
            self.assertEqual(_run_cli(["pack", str(source), "--out", str(capsule), "--sign-key-env", "CAPSULE_HMAC_KEY"]), 0)
            text = capsule.read_text(encoding="utf-8")
            text = text.replace("c2lnbmVkIHN0YXRl", "c2lnbmVkIHN0YXRm", 1)
            capsule.write_text(text, encoding="utf-8")

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--key-env", "CAPSULE_HMAC_KEY"])

            self.assertNotEqual(status, 0)
            self.assertEqual(stdout, "")
            self.assertIn("signature verification failed", stderr)

    def test_cli_returns_nonzero_on_invalid_capsule(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule = Path(tmp) / "bad.txt"
            capsule.write_text("not a capsule", encoding="utf-8")

            self.assertNotEqual(_run_cli(["verify", str(capsule)]), 0)

    def test_cli_detects_sha_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            envelope = build_envelope(b"payload")
            capsule = Path(tmp) / "bad-sha.txt"
            capsule.write_text(render_envelope(envelope).replace(envelope.payload_sha256, "0" * 64), encoding="utf-8")

            self.assertNotEqual(_run_cli(["verify", str(capsule)]), 0)

    def test_cli_lists_codecs(self) -> None:
        self.assertEqual(_run_cli(["codecs"]), 0)

    def test_verify_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule = Path(tmp) / "capsule.txt"
            envelope = build_envelope(b"payload")
            capsule.write_text(render_envelope(envelope), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["verify", str(capsule), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["verification"], "ok")
            self.assertEqual(payload["payload_bytes"], 7)
            self.assertEqual(payload["payload_sha256"], envelope.payload_sha256)

    def test_pack_inspect_json_includes_capsule_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "patch.diff"
            capsule = root / "capsule.txt"
            source.write_text("diff", encoding="utf-8")

            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--created-by",
                        "agent-a",
                        "--task-id",
                        "abc123",
                        "--requested-capability",
                        "read_files",
                        "--requested-capability",
                        "run_tests",
                        "--policy-hint",
                        "sandbox_required=true",
                        "--policy-hint",
                        "network_egress=false",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["inspect", str(capsule), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            manifest = payload["capsule_manifest"]
            self.assertEqual(manifest["capsule_type"], "agent_handoff")
            self.assertEqual(manifest["created_by"], "agent-a")
            self.assertEqual(manifest["task_id"], "abc123")
            self.assertEqual(manifest["delivery"], {"mode": "inline"})
            self.assertEqual(manifest["requested_capabilities"], ["read_files", "run_tests"])
            self.assertEqual(manifest["policy_hints"], {"network_egress": False, "sandbox_required": True})
            self.assertEqual(manifest["files"][0]["path"], "patch.diff")
            self.assertEqual(manifest["files"][0]["bytes"], 4)

    def test_pack_supports_attachment_delivery_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.txt"
            capsule = root / "capsule.txt"
            source.write_text("payload", encoding="utf-8")

            self.assertEqual(
                _run_cli(["pack", str(source), "--out", str(capsule), "--delivery-mode", "attachment"]),
                0,
            )

            status, stdout, stderr = _capture_cli(["inspect", str(capsule), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["capsule_manifest"]["delivery"], {"mode": "attachment"})

    def test_reference_json_output_includes_uri_hash_and_signature_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            capsule = root / "capsule.txt"
            envelope = build_envelope(
                b"payload",
                delivery_mode="reference",
                delivery_uri="https://example.test/capsules/capsule.txt",
                created_at="2026-05-09T00:00:00Z",
            )
            capsule.write_text(render_envelope(envelope), encoding="utf-8")

            status, stdout, stderr = _capture_cli(
                [
                    "reference",
                    str(capsule),
                    "--uri",
                    "https://example.test/capsules/capsule.txt",
                    "--json",
                ]
            )

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["reference_type"], "agent_capsule_reference")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["capsule_uri"], "https://example.test/capsules/capsule.txt")
            self.assertEqual(payload["payload_sha256"], envelope.payload_sha256)
            self.assertEqual(payload["signature"]["mode"], "none")
            self.assertEqual(
                payload["capsule_manifest"]["delivery"],
                {"mode": "reference", "uri": "https://example.test/capsules/capsule.txt"},
            )

    def test_inspect_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            capsule = Path(tmp) / "capsule.txt"
            envelope = build_envelope(b"payload")
            capsule.write_text(render_envelope(envelope), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["inspect", str(capsule), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["verification_status"], "ok")
            self.assertEqual(payload["codec"], "base64")
            self.assertIn("unsigned capsule", payload["risk_notes"][0])

    def test_scan_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "message.txt"
            text_file.write_text(render_envelope(build_envelope(b"payload")), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["scan", str(text_file), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["report_type"], "agent_capsule_governance_scan")
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["disposition"], "allow")
            self.assertEqual(payload["capsules_detected"], 1)
            self.assertEqual(payload["valid_capsules"], 1)
            self.assertEqual(payload["risk_level"], "low")
            self.assertTrue(payload["policy"]["require_known_codec"])
            self.assertEqual(payload["findings"], [])

    def test_scan_json_includes_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "message.txt"
            text_file.write_text("prefix\n" + ("A" * 120), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["scan", str(text_file), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["disposition"], "review")
            self.assertEqual(payload["findings"][0]["type"], "dense_base64_like")
            self.assertEqual(payload["findings"][0]["line"], 2)

    def test_scan_human_output_is_governance_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "message.txt"
            text_file.write_text("prefix\n" + ("A" * 120), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["scan", str(text_file)])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            self.assertIn("Agent Capsule Governance Report", stdout)
            self.assertIn("disposition: review", stdout)
            self.assertIn("finding: [MEDIUM] dense_base64_like", stdout)

    def test_ingest_json_output_is_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            inline_capsule = render_envelope(build_envelope(b"inline payload", filename="inline.txt"))
            ref_capsule = render_envelope(build_envelope(b"reference payload", filename="reference.txt"))
            ref_sha = hashlib.sha256(ref_capsule.encode("utf-8")).hexdigest()
            transcript = root / "thread.txt"
            transcript.write_text(
                (
                    "message start\n"
                    f"{inline_capsule}\n"
                    + json.dumps(
                        {
                            "reference_type": "agent_capsule_reference",
                            "schema_version": 1,
                            "capsule_uri": "https://example.test/capsules/ref-1.txt",
                            "capsule_sha256": ref_sha,
                        }
                    )
                    + "\n-----BEGIN AGENT CAPSULE-----\ntruncated\n"
                ),
                encoding="utf-8",
            )
            out = root / "decoded"

            def _mock_fetch(uri, *, expected_sha256=None, save_path=None, resumable=False):
                self.assertEqual(uri, "https://example.test/capsules/ref-1.txt")
                self.assertEqual(expected_sha256, ref_sha)
                if save_path:
                    save_path.write_bytes(ref_capsule.encode("utf-8"))
                return ref_capsule.encode("utf-8")

            with patch("agentcapsule.receiver.fetch_capsule", side_effect=_mock_fetch):
                status, stdout, stderr = _capture_cli(["ingest", str(transcript), "--out", str(out), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["malformed_blocks"], 1)
            self.assertEqual(len(payload["inline_capsules"]), 1)
            self.assertEqual(len(payload["references"]), 1)
            self.assertEqual(payload["references"][0]["status"], "unpacked")
            self.assertEqual(len(payload["unpacked_files"]), 2)

    def test_codecs_json_output(self) -> None:
        status, stdout, stderr = _capture_cli(["codecs", "--json"])

        self.assertEqual(status, 0)
        self.assertEqual(stderr, "")
        payload = json.loads(stdout)
        self.assertEqual(
            [codec["name"] for codec in payload["codecs"]],
            ["base64", "lmcodec-fixed", "lmcodec-ngram-v2"],
        )

    def test_ngram_v2_inspect_json_includes_codec_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "payload.bin"
            capsule = root / "capsule.txt"
            source.write_bytes(b"ngram-v2")
            self.assertEqual(
                _run_cli(
                    [
                        "pack",
                        str(source),
                        "--out",
                        str(capsule),
                        "--codec",
                        "lmcodec-ngram-v2",
                        "--model",
                        "tests/fixtures/ngram_model_v1.json",
                    ]
                ),
                0,
            )

            status, stdout, stderr = _capture_cli(["inspect", str(capsule), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["codec"], "lmcodec-ngram-v2")
            self.assertEqual(payload["codec_metadata"]["lmcodec_model_type"], "ngram-v1")
            self.assertEqual(payload["codec_metadata"]["lmcodec_model_encoding"], "inline-base64-json")


def _run_cli(argv: list[str]) -> int:
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        return main(argv)


def _capture_cli(argv: list[str]) -> tuple[int, str, str]:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        status = main(argv)
    return status, stdout.getvalue().strip(), stderr.getvalue().strip()


if __name__ == "__main__":
    unittest.main()
