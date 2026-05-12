import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentHandoffDashboardTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("cryptography") is None, "optional signing extra is not installed")
    def test_dashboard_renderer_outputs_static_html(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            matrix = subprocess.run(
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
            self.assertEqual(matrix.returncode, 0, matrix.stderr + matrix.stdout)
            evaluation = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "evaluate_agent_handoff_transcript.py"),
                    "--events",
                    str(Path(tmp) / "events.jsonl"),
                    "--message",
                    str(Path(tmp) / "agent-a-to-agent-b-message.txt"),
                    "--out",
                    str(Path(tmp) / "evaluation.json"),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(evaluation.returncode, 0, evaluation.stderr + evaluation.stdout)
            dashboard = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "render_agent_handoff_dashboard.py"),
                    "--input-dir",
                    tmp,
                    "--out",
                    str(Path(tmp) / "dashboard.html"),
                ],
                cwd=ROOT,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(dashboard.returncode, 0, dashboard.stderr + dashboard.stdout)
            html = (Path(tmp) / "dashboard.html").read_text(encoding="utf-8")
            self.assertIn("Agent Handoff Observability", html)
            self.assertIn("trusted_signature_present", html)
            self.assertIn("wrong_agent_key_block", html)
            self.assertIn("policy-matrix-report.json", html)


if __name__ == "__main__":
    unittest.main()

