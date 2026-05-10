#!/usr/bin/env python3
"""Run a local Agent A to Agent B handoff experiment."""

from __future__ import annotations

import argparse
import filecmp
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
AGENT_A_WORKSPACE = ROOT_DIR / "examples" / "agent_handoff_demo" / "agent_a_workspace"
AGENT_B_WORKSPACE = ROOT_DIR / "examples" / "agent_handoff_demo" / "agent_b_workspace"
AGENT_B_POLICY = AGENT_B_WORKSPACE / "policy-require-agent-a-registry.json"
KEY_ID = "agent-a-demo-2026q2"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", help="directory for generated capsules, decoded files, and events.jsonl")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir) if args.out_dir else Path(tempfile.mkdtemp(prefix="agent-handoff-demo-"))
    out_dir.mkdir(parents=True, exist_ok=True)
    events_path = out_dir / "events.jsonl"
    trace_id = f"agent-handoff-{uuid.uuid4().hex[:12]}"

    with events_path.open("w", encoding="utf-8") as events:
        if importlib.util.find_spec("cryptography") is None:
            emit(
                events,
                trace_id,
                "dependency_check",
                "review",
                result={
                    "status": "skipped",
                    "reason": "optional Ed25519 dependency is not installed",
                    "install": 'python3 -m pip install -e ".[signing]"',
                },
            )
            print(f"Agent handoff demo skipped: optional signing extra is not installed")
            print(f"events jsonl: {events_path}")
            return 0

        private_key = out_dir / "agent-a.key"
        public_key = out_dir / "agent-a.pub"
        registry = out_dir / "agent-b-trust-registry.json"
        capsule = out_dir / "agent-a-handoff.capsule.txt"
        message = out_dir / "agent-a-to-agent-b-message.txt"
        decoded = out_dir / "agent-b-decoded"

        run_cli(
            ["keys", "generate", "--private-key", str(private_key), "--public-key", str(public_key), "--force"],
            events,
            trace_id,
        )
        emit(
            events,
            trace_id,
            "create_agent_a_keys",
            "allow",
            subject=str(out_dir),
            result={"private_key": str(private_key), "public_key": str(public_key), "signature_key_id": KEY_ID},
        )

        registry_result = run_cli(
            [
                "keys",
                "registry-entry",
                "--key-id",
                KEY_ID,
                "--public-key",
                str(public_key),
                "--publisher",
                "Agent A Demo",
            ],
            events,
            trace_id,
        )
        registry.write_text(registry_result.stdout, encoding="utf-8")
        emit(
            events,
            trace_id,
            "create_agent_b_trust_registry",
            "allow",
            subject=str(registry),
            result={"registry": str(registry), "trusted_key_id": KEY_ID},
        )

        run_cli(
            [
                "pack",
                str(AGENT_A_WORKSPACE),
                "--out",
                str(capsule),
                "--sign-ed25519-key",
                str(private_key),
                "--signature-key-id",
                KEY_ID,
                "--no-inline-public-key",
            ],
            events,
            trace_id,
        )
        emit(
            events,
            trace_id,
            "pack_signed_handoff_capsule",
            "allow",
            subject=str(capsule),
            result={"capsule": str(capsule), "source_workspace": str(AGENT_A_WORKSPACE)},
        )

        compose_message(capsule, message)
        emit(
            events,
            trace_id,
            "compose_text_handoff_message",
            "allow",
            subject=str(message),
            result={"message": str(message), "message_sha256": sha256_file(message)},
        )

        scan = run_cli_json(
            [
                "scan",
                str(message),
                "--policy",
                str(AGENT_B_POLICY),
                "--signature-registry",
                str(registry),
                "--audit-json",
            ],
            events,
            trace_id,
            step="scan_text_message",
        )

        verify = run_cli_json(
            [
                "verify",
                str(capsule),
                "--policy",
                str(AGENT_B_POLICY),
                "--signature-registry",
                str(registry),
                "--audit-json",
            ],
            events,
            trace_id,
            step="verify_handoff_capsule",
        )

        unpack = run_cli_json(
            [
                "unpack",
                str(capsule),
                "--out",
                str(decoded),
                "--policy",
                str(AGENT_B_POLICY),
                "--signature-registry",
                str(registry),
                "--audit-json",
            ],
            events,
            trace_id,
            step="unpack_handoff_bundle",
        )

        comparison = compare_trees(AGENT_A_WORKSPACE, decoded)
        disposition = "allow" if comparison["match"] else "block"
        emit(
            events,
            trace_id,
            "compare_decoded_artifacts",
            disposition,
            subject=str(decoded),
            result=comparison,
        )

    print(f"trace id: {trace_id}")
    print(f"agent a workspace: {AGENT_A_WORKSPACE}")
    print(f"agent b workspace: {AGENT_B_WORKSPACE}")
    print(f"message: {message}")
    print(f"capsule: {capsule}")
    print(f"decoded: {decoded}")
    print(f"events jsonl: {events_path}")
    print(f"scan disposition: {scan['disposition']}")
    print(f"verify disposition: {verify['disposition']}")
    print(f"unpack disposition: {unpack['disposition']}")
    print(f"artifact comparison: {'ok' if comparison['match'] else 'failed'}")
    return 0 if comparison["match"] else 1


class CliResult:
    def __init__(self, args: list[str], returncode: int, stdout: str, stderr: str) -> None:
        self.args = args
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_cli(args: list[str], events, trace_id: str, *, expect: int = 0) -> CliResult:
    command = [sys.executable, "-m", "agentcapsule.cli", *args]
    env = os.environ.copy()
    src_path = str(ROOT_DIR / "src")
    env["PYTHONPATH"] = src_path if not env.get("PYTHONPATH") else f"{src_path}{os.pathsep}{env['PYTHONPATH']}"
    completed = subprocess.run(command, cwd=ROOT_DIR, env=env, text=True, capture_output=True, check=False)
    result = CliResult(args, completed.returncode, completed.stdout, completed.stderr)
    if completed.returncode != expect:
        emit(
            events,
            trace_id,
            "cli_command_failed",
            "block",
            result={
                "args": args,
                "returncode": completed.returncode,
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            },
        )
        raise SystemExit(completed.returncode)
    return result


def run_cli_json(args: list[str], events, trace_id: str, *, step: str) -> dict[str, Any]:
    result = run_cli(args, events, trace_id)
    try:
        event = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        emit(
            events,
            trace_id,
            "cli_json_parse_failed",
            "block",
            result={"args": args, "stdout": result.stdout, "error": str(exc)},
        )
        raise SystemExit(2) from exc
    event["trace_type"] = "agent_to_agent_handoff_demo"
    event["trace_id"] = trace_id
    event["step"] = step
    events.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
    return event


def emit(
    events,
    trace_id: str,
    operation: str,
    disposition: str,
    *,
    subject: str | None = None,
    result: dict[str, Any] | None = None,
) -> None:
    event = {
        "event_type": "agent_handoff_trace",
        "schema_version": 1,
        "trace_type": "agent_to_agent_handoff_demo",
        "trace_id": trace_id,
        "operation": operation,
        "disposition": disposition,
        "subject": subject,
        "result": result or {},
    }
    events.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")


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


def compare_trees(source: Path, decoded: Path) -> dict[str, Any]:
    source_files = file_hashes(source)
    decoded_files = file_hashes(decoded)
    missing = sorted(set(source_files) - set(decoded_files))
    extra = sorted(set(decoded_files) - set(source_files))
    mismatched = sorted(path for path in set(source_files) & set(decoded_files) if source_files[path] != decoded_files[path])
    return {
        "match": not missing and not extra and not mismatched,
        "source_files": source_files,
        "decoded_files": decoded_files,
        "missing": missing,
        "extra": extra,
        "mismatched": mismatched,
        "directory_cmp_equal": filecmp.dircmp(source, decoded).left_only == []
        and filecmp.dircmp(source, decoded).right_only == []
        and filecmp.dircmp(source, decoded).diff_files == [],
    }


def file_hashes(root: Path) -> dict[str, str]:
    hashes = {}
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        hashes[path.relative_to(root).as_posix()] = sha256_file(path)
    return hashes


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
