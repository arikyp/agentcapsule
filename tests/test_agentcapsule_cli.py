import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path

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
            self.assertEqual(payload["capsules_detected"], 1)
            self.assertEqual(payload["valid_capsules"], 1)
            self.assertEqual(payload["risk_level"], "low")
            self.assertEqual(payload["findings"], [])

    def test_scan_json_includes_findings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            text_file = Path(tmp) / "message.txt"
            text_file.write_text("prefix\n" + ("A" * 120), encoding="utf-8")

            status, stdout, stderr = _capture_cli(["scan", str(text_file), "--json"])

            self.assertEqual(status, 0)
            self.assertEqual(stderr, "")
            payload = json.loads(stdout)
            self.assertEqual(payload["findings"][0]["type"], "dense_base64_like")
            self.assertEqual(payload["findings"][0]["line"], 2)

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
