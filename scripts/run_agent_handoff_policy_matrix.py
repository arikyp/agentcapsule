#!/usr/bin/env python3
"""Run enterprise policy scenarios against the Agent A to Agent B handoff demo."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
AGENT_A_WORKSPACE = ROOT_DIR / "examples" / "agent_handoff_demo" / "agent_a_workspace"
AGENT_B_WORKSPACE = ROOT_DIR / "examples" / "agent_handoff_demo" / "agent_b_workspace"
MATRIX_CONFIG = AGENT_B_WORKSPACE / "policy-matrix.json"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", help="directory for generated matrix artifacts")
    parser.add_argument("--matrix", default=str(MATRIX_CONFIG), help="policy matrix JSON")
    parser.add_argument("--pretty", action="store_true", help="pretty-print report JSON")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.mkdtemp(prefix="agent-handoff-policy-matrix-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    report_path = out_dir / "policy-matrix-report.json"
    events_path = out_dir / "policy-matrix-events.jsonl"

    if importlib.util.find_spec("cryptography") is None:
        report = {
            "report_type": "agent_handoff_policy_matrix",
            "schema_version": 1,
            "disposition": "review",
            "status": "skipped",
            "reason": "optional Ed25519 dependency is not installed",
            "install": 'python3 -m pip install -e ".[signing]"',
            "out_dir": str(out_dir),
        }
        write_report(report_path, report, pretty=args.pretty)
        print_report(report, pretty=args.pretty)
        return 0

    run_experiment(out_dir)
    signed_capsule = out_dir / "agent-a-handoff.capsule.txt"
    signed_message = out_dir / "agent-a-to-agent-b-message.txt"
    registry = out_dir / "agent-b-trust-registry.json"
    unsigned_capsule = out_dir / "unsigned-agent-a-handoff.capsule.txt"
    unsigned_message = out_dir / "unsigned-agent-a-to-agent-b-message.txt"

    run_cli(["pack", str(AGENT_A_WORKSPACE), "--out", str(unsigned_capsule)])
    compose_message(unsigned_capsule, unsigned_message)

    matrix = load_matrix(Path(args.matrix))
    scenario_results = []
    with events_path.open("w", encoding="utf-8") as events:
        for scenario in matrix["scenarios"]:
            result = run_scenario(
                scenario,
                out_dir=out_dir,
                signed_capsule=signed_capsule,
                signed_message=signed_message,
                unsigned_capsule=unsigned_capsule,
                unsigned_message=unsigned_message,
                registry=registry,
            )
            scenario_results.append(result)
            events.write(json.dumps(result, sort_keys=True, separators=(",", ":")) + "\n")

    passed = all(result["passed"] for result in scenario_results)
    report = {
        "report_type": "agent_handoff_policy_matrix",
        "schema_version": 1,
        "disposition": "allow" if passed else "block",
        "matrix": str(Path(args.matrix)),
        "out_dir": str(out_dir),
        "events_path": str(events_path),
        "scenario_count": len(scenario_results),
        "passed_scenarios": sum(1 for result in scenario_results if result["passed"]),
        "failed_scenarios": sum(1 for result in scenario_results if not result["passed"]),
        "scenarios": scenario_results,
    }
    write_report(report_path, report, pretty=args.pretty)
    print_report(report, pretty=args.pretty)
    return 0 if passed else 1


def run_experiment(out_dir: Path) -> None:
    command = [sys.executable, str(ROOT_DIR / "scripts" / "run_agent_handoff_experiment.py"), "--out-dir", str(out_dir)]
    completed = subprocess.run(command, cwd=ROOT_DIR, env=env(), text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.stderr + completed.stdout)


def run_scenario(
    scenario: dict[str, Any],
    *,
    out_dir: Path,
    signed_capsule: Path,
    signed_message: Path,
    unsigned_capsule: Path,
    unsigned_message: Path,
    registry: Path,
) -> dict[str, Any]:
    name = str(scenario["name"])
    operation = str(scenario["operation"])
    expected = str(scenario["expected_disposition"])
    policy = AGENT_B_WORKSPACE / str(scenario["policy"])
    artifact = str(scenario["artifact"])
    capsule = signed_capsule if artifact == "signed" else unsigned_capsule
    message = signed_message if artifact == "signed" else unsigned_message
    command = command_for_operation(
        operation=operation,
        capsule=capsule,
        message=message,
        policy=policy,
        registry=registry,
        out_dir=out_dir / f"decoded-{name}",
    )
    completed = run_cli(command)
    event = parse_audit_stdout(completed.stdout)
    observed = event.get("disposition", "unknown")
    return {
        "event_type": "agent_handoff_policy_matrix_scenario",
        "schema_version": 1,
        "name": name,
        "operation": operation,
        "artifact": artifact,
        "policy": str(policy),
        "expected_disposition": expected,
        "observed_disposition": observed,
        "passed": observed == expected,
        "returncode": completed.returncode,
        "audit_event": event,
    }


def command_for_operation(
    *,
    operation: str,
    capsule: Path,
    message: Path,
    policy: Path,
    registry: Path,
    out_dir: Path,
) -> list[str]:
    if operation == "scan":
        return [
            "scan",
            str(message),
            "--policy",
            str(policy),
            "--signature-registry",
            str(registry),
            "--audit-json",
        ]
    if operation == "verify":
        return [
            "verify",
            str(capsule),
            "--policy",
            str(policy),
            "--signature-registry",
            str(registry),
            "--audit-json",
        ]
    if operation == "unpack":
        return [
            "unpack",
            str(capsule),
            "--out",
            str(out_dir),
            "--policy",
            str(policy),
            "--signature-registry",
            str(registry),
            "--audit-json",
        ]
    raise SystemExit(f"unsupported matrix operation: {operation}")


class CliResult:
    def __init__(self, returncode: int, stdout: str, stderr: str) -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_cli(args: list[str]) -> CliResult:
    command = [sys.executable, "-m", "agentcapsule.cli", *args]
    completed = subprocess.run(command, cwd=ROOT_DIR, env=env(), text=True, capture_output=True, check=False)
    if completed.returncode not in {0, 2}:
        raise SystemExit(completed.stderr + completed.stdout)
    return CliResult(completed.returncode, completed.stdout, completed.stderr)


def load_matrix(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("scenarios"), list):
        raise SystemExit("policy matrix JSON must contain a scenarios list")
    return data


def parse_audit_stdout(stdout: str) -> dict[str, Any]:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"matrix command did not emit JSON: {stdout}") from exc
    if not isinstance(data, dict):
        raise SystemExit("matrix command JSON must be an object")
    return data


def compose_message(capsule: Path, message: Path) -> None:
    summary = (AGENT_A_WORKSPACE / "handoff_summary.md").read_text(encoding="utf-8")
    capsule_text = capsule.read_text(encoding="utf-8")
    message.write_text(
        "\n".join(
            [
                "Agent A -> Agent B handoff",
                "",
                "Human-readable summary:",
                "",
                summary.strip(),
                "",
                "Exact machine-readable handoff capsule:",
                "",
                capsule_text.strip(),
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )


def write_report(path: Path, report: dict[str, Any], *, pretty: bool) -> None:
    path.write_text(format_json(report, pretty=pretty) + "\n", encoding="utf-8")


def print_report(report: dict[str, Any], *, pretty: bool) -> None:
    print(format_json(report, pretty=pretty))


def format_json(data: dict[str, Any], *, pretty: bool) -> str:
    return json.dumps(data, indent=2 if pretty else None, sort_keys=True, separators=None if pretty else (",", ":"))


def env() -> dict[str, str]:
    data = os.environ.copy()
    src_path = str(ROOT_DIR / "src")
    legacy_src_path = str(ROOT_DIR / "legacy" / "lmcodec" / "src")
    prefix = f"{src_path}{os.pathsep}{legacy_src_path}"
    data["PYTHONPATH"] = prefix if not data.get("PYTHONPATH") else f"{prefix}{os.pathsep}{data['PYTHONPATH']}"
    return data


if __name__ == "__main__":
    raise SystemExit(main())
