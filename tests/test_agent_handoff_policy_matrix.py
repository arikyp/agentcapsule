import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentHandoffPolicyMatrixTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("cryptography") is None, "optional signing extra is not installed")
    def test_policy_matrix_expected_dispositions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_agent_handoff_policy_matrix.py"),
                    "--out-dir",
                    tmp,
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
            report = json.loads((Path(tmp) / "policy-matrix-report.json").read_text(encoding="utf-8"))
            self.assertEqual(report["disposition"], "allow")
            self.assertEqual(report["failed_scenarios"], 0)
            observed = {scenario["name"]: scenario["observed_disposition"] for scenario in report["scenarios"]}
            self.assertEqual(observed["observe_signed_bundle"], "allow")
            self.assertEqual(observed["strict_registry_signed_bundle"], "allow")
            self.assertEqual(observed["strict_message_scan"], "review")
            self.assertEqual(observed["wrong_agent_key_block"], "block")
            self.assertEqual(observed["payload_limit_block"], "block")
            self.assertEqual(observed["unsigned_handoff_block"], "block")


if __name__ == "__main__":
    unittest.main()

