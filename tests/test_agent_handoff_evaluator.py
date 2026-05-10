import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.evaluate_agent_handoff_transcript import evaluate_transcript


ROOT = Path(__file__).resolve().parents[1]


class AgentHandoffEvaluatorTests(unittest.TestCase):
    @unittest.skipIf(importlib.util.find_spec("cryptography") is None, "optional signing extra is not installed")
    def test_evaluator_allows_complete_handoff_trace(self) -> None:
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

            report = evaluate_transcript(
                events_path=Path(tmp) / "events.jsonl",
                message_path=Path(tmp) / "agent-a-to-agent-b-message.txt",
            )

            self.assertEqual(report["disposition"], "allow")
            self.assertEqual(report["score"], 100)
            checks = {check["id"]: check["status"] for check in report["checks"]}
            self.assertEqual(checks["trusted_signature_present"], "pass")
            self.assertEqual(checks["artifact_compare_passed"], "pass")

    def test_evaluator_blocks_missing_trusted_signature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            message = root / "message.txt"
            events = root / "events.jsonl"
            message.write_text(
                "Human-readable summary:\ncontinue work\n\n"
                "-----BEGIN AGENT CAPSULE-----\n"
                "capsule_version: 0.1\n"
                "-----END AGENT CAPSULE-----\n",
                encoding="utf-8",
            )
            write_jsonl(
                events,
                [
                    {
                        "event_type": "agent_capsule_audit",
                        "trace_id": "trace-1",
                        "step": "scan_text_message",
                        "disposition": "review",
                        "result": {"valid_capsules": 1, "risk_level": "medium"},
                    },
                    {
                        "event_type": "agent_capsule_audit",
                        "trace_id": "trace-1",
                        "step": "verify_handoff_capsule",
                        "disposition": "allow",
                        "result": {"verification": "ok", "signature_trust": {"status": "untrusted"}},
                    },
                    {
                        "event_type": "agent_capsule_audit",
                        "trace_id": "trace-1",
                        "step": "unpack_handoff_bundle",
                        "disposition": "allow",
                        "result": {"files_written": ["decoded/task_state.json"]},
                    },
                    {
                        "event_type": "agent_handoff_trace",
                        "trace_id": "trace-1",
                        "operation": "compare_decoded_artifacts",
                        "disposition": "allow",
                        "result": {"match": True, "source_files": {"task_state.json": "abc"}},
                    },
                ],
            )

            report = evaluate_transcript(events_path=events, message_path=message)

            self.assertEqual(report["disposition"], "block")
            checks = {check["id"]: check["status"] for check in report["checks"]}
            self.assertEqual(checks["trusted_signature_present"], "fail")


def write_jsonl(path: Path, events: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n" for event in events),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()

