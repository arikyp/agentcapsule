import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AgentHandoffDemoTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("cryptography") is None, "optional signing extra is not installed")
    def test_agent_handoff_experiment_emits_trace_and_compares_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["PYTHONPATH"] = str(ROOT / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "run_agent_handoff_experiment.py"),
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
            events = [
                json.loads(line)
                for line in (Path(tmp) / "events.jsonl").read_text(encoding="utf-8").splitlines()
            ]
            operations = {event.get("operation") for event in events}
            steps = {event.get("step") for event in events}
            self.assertIn("create_agent_a_keys", operations)
            self.assertIn("create_agent_b_trust_registry", operations)
            self.assertIn("pack_signed_handoff_capsule", operations)
            self.assertIn("compose_text_handoff_message", operations)
            self.assertIn("scan_text_message", steps)
            self.assertIn("verify_handoff_capsule", steps)
            self.assertIn("unpack_handoff_bundle", steps)

            comparison = next(event for event in events if event.get("operation") == "compare_decoded_artifacts")
            self.assertEqual(comparison["disposition"], "allow")
            self.assertTrue(comparison["result"]["match"])

            verify = next(event for event in events if event.get("step") == "verify_handoff_capsule")
            self.assertEqual(verify["disposition"], "allow")
            self.assertEqual(verify["result"]["signature_trust"]["status"], "trusted")

            message = (Path(tmp) / "agent-a-to-agent-b-message.txt").read_text(encoding="utf-8")
            self.assertIn("Human-readable summary:", message)
            self.assertIn("-----BEGIN AGENT CAPSULE-----", message)


if __name__ == "__main__":
    unittest.main()

