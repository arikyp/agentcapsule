import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import profile_experiment


class ProfileExperimentTests(unittest.TestCase):
    def test_profile_experiment_runs_config_and_prints_stats(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            payload = root / "payload.bin"
            output_dir = root / "run"
            config = root / "config.json"
            payload.write_bytes(b"profile")
            config.write_text(
                json.dumps(
                    {
                        "experiment_name": "profile-fixed",
                        "payload_path": str(payload),
                        "model": {"type": "fixed"},
                        "shape_settings": {},
                        "max_steps": 100000,
                        "run_golden_tests": False,
                        "output_dir": str(output_dir),
                    }
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = profile_experiment.main([str(config), "--limit", "5"])

            self.assertEqual(code, 2)
            self.assertIn("function calls", stdout.getvalue())
            self.assertTrue((output_dir / "result.json").exists())


if __name__ == "__main__":
    unittest.main()
