import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import compare_models, sweep_shaping


ROOT = Path(__file__).resolve().parents[1]


class BenchmarkJsonTests(unittest.TestCase):
    def test_compare_models_writes_json_result_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = root / "payload.bin"
            output = root / "compare.json"
            payload.write_bytes(b"benchmark-json")

            with contextlib.redirect_stdout(io.StringIO()):
                code = compare_models.main(
                    [
                        "--payload",
                        str(payload),
                        "--json-out",
                        str(output),
                        "--preview-chars",
                        "12",
                    ]
                )

            self.assertEqual(code, 0)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(document["schema_version"], 1)
            self.assertIn("timestamp_utc", document)
            self.assertIn("git_commit", document)
            self.assertEqual(document["payload"]["path"], str(payload))
            self.assertEqual(document["payload"]["bytes"], len(b"benchmark-json"))
            self.assertEqual(len(document["payload"]["sha256"]), 64)

            result = document["results"][0]
            self.assertEqual(result["name"], "fixed")
            self.assertEqual(result["payload_path"], str(payload))
            self.assertEqual(result["model_type"], "fixed-v1")
            self.assertTrue(result["roundtrip_success"])
            self.assertIsNone(result["error_message"])
            self.assertGreater(result["carrier_chars"], 0)
            self.assertGreater(result["full_armour_chars"], result["carrier_chars"])
            self.assertGreater(result["bits_per_carrier_char"], 0.0)
            self.assertGreaterEqual(result["encode_seconds"], 0.0)
            self.assertGreaterEqual(result["decode_seconds"], 0.0)
            self.assertEqual(result["convergence_failure_count"], 0)
            self.assertIsNotNone(result["carrier_quality"])
            self.assertGreater(result["carrier_quality"]["unique_character_count"], 0)
            self.assertGreater(result["carrier_quality"]["longest_repeated_run"], 0)

    def test_sweep_shaping_writes_failure_json_result_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = root / "payload.bin"
            quality_text = root / "quality.txt"
            output = root / "sweep.json"
            payload.write_bytes(b"x")
            quality_text.write_text("abc abc", encoding="utf-8")

            with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                code = sweep_shaping.main(
                    [
                        "--model",
                        str(ROOT / "tests" / "fixtures" / "transformer_model_v1.json"),
                        "--payload",
                        str(payload),
                        "--quality-text",
                        str(quality_text),
                        "--uniform-mixes",
                        "2.0",
                        "--temperatures",
                        "1.25",
                        "--min-probs",
                        "0.0",
                        "--json-out",
                        str(output),
                        "--preview-chars",
                        "8",
                    ]
                )

            self.assertEqual(code, 2)
            document = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(document["schema_version"], 1)
            self.assertEqual(document["payload"]["path"], str(payload))
            self.assertEqual(document["model"]["type"], "transformer-rf-v1")
            self.assertEqual(document["quality_text"]["path"], str(quality_text))

            result = document["results"][0]
            self.assertFalse(result["roundtrip_success"])
            self.assertEqual(result["payload_bytes"], 1)
            self.assertEqual(result["model_path"], str(ROOT / "tests" / "fixtures" / "transformer_model_v1.json"))
            self.assertIsNotNone(result["model_fingerprint"])
            self.assertIsNotNone(result["error_message"])
            self.assertIsNone(result["carrier_chars"])


if __name__ == "__main__":
    unittest.main()
