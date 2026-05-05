import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import run_experiment


class RunExperimentTests(unittest.TestCase):
    def test_fixed_config_writes_artifacts_and_passing_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = root / "payload.bin"
            quality = root / "quality.txt"
            output_dir = root / "run"
            config = root / "config.json"
            payload.write_bytes(b"bounded experiment")
            quality.write_text("abc abc", encoding="utf-8")
            config.write_text(
                json.dumps(
                    {
                        "experiment_name": "test-fixed",
                        "payload_path": str(payload),
                        "model": {"type": "fixed"},
                        "shape_settings": {},
                        "max_steps": 100000,
                        "quality_text_path": str(quality),
                        "promotion_gate": {"min_entropy_bits": 5.9},
                        "output_dir": str(output_dir),
                    }
                ),
                encoding="utf-8",
            )

            with contextlib.redirect_stdout(io.StringIO()):
                code = run_experiment.main([str(config)])

            self.assertEqual(code, 0)
            result_path = output_dir / "result.json"
            self.assertTrue(result_path.exists())
            self.assertTrue((output_dir / "carrier.txt").exists())
            self.assertEqual((output_dir / "decoded_payload.bin").read_bytes(), payload.read_bytes())

            result = json.loads(result_path.read_text(encoding="utf-8"))
            self.assertEqual(result["experiment_name"], "test-fixed")
            self.assertTrue(result["roundtrip_success"])
            self.assertTrue(result["promotion"]["passed"])
            self.assertTrue(result["promotion"]["checks"]["decoded_sha256_matches"])
            self.assertEqual(result["carrier_diversity"]["unique_character_count"], len(result["carrier_diversity"]["character_frequency"]))
            self.assertGreater(result["carrier_diversity"]["longest_repeated_run"], 0)
            self.assertIsNotNone(result["carrier_diversity"]["char_frequency_l1_divergence"])
            self.assertIsNotNone(result["carrier_diversity"]["char_frequency_kl_bits"])


if __name__ == "__main__":
    unittest.main()
