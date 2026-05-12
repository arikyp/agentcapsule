#!/usr/bin/env python3
"""Render a static observability dashboard for Agent Capsule handoff artifacts."""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any


REPORT_TYPE = "agent_handoff_observability_dashboard"
SCHEMA_VERSION = 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", help="directory containing handoff demo artifacts")
    parser.add_argument("--events", help="handoff events.jsonl")
    parser.add_argument("--evaluation", help="handoff evaluation.json")
    parser.add_argument("--policy-matrix", help="policy-matrix-report.json")
    parser.add_argument("--out", required=True, help="dashboard HTML output path")
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir) if args.input_dir else None
    events_path = Path(args.events) if args.events else _optional_path(input_dir, "events.jsonl")
    evaluation_path = Path(args.evaluation) if args.evaluation else _optional_path(input_dir, "evaluation.json")
    matrix_path = Path(args.policy_matrix) if args.policy_matrix else _optional_path(input_dir, "policy-matrix-report.json")
    out_path = Path(args.out)

    dashboard = build_dashboard(
        events_path=events_path,
        evaluation_path=evaluation_path,
        matrix_path=matrix_path,
        input_dir=input_dir,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_html(dashboard), encoding="utf-8")
    print(f"dashboard: {out_path}")
    print(f"disposition: {dashboard['disposition']}")
    print(f"events: {dashboard['summary']['events']}")
    print(f"policy scenarios: {dashboard['summary']['policy_scenarios']}")
    return 0 if dashboard["disposition"] in {"allow", "review"} else 1


def build_dashboard(
    *,
    events_path: Path | None,
    evaluation_path: Path | None,
    matrix_path: Path | None,
    input_dir: Path | None = None,
) -> dict[str, Any]:
    events = load_jsonl(events_path) if events_path and events_path.exists() else []
    evaluation = load_json(evaluation_path) if evaluation_path and evaluation_path.exists() else None
    matrix = load_json(matrix_path) if matrix_path and matrix_path.exists() else None
    dispositions = [event.get("disposition") for event in events if isinstance(event.get("disposition"), str)]
    if isinstance(evaluation, dict) and isinstance(evaluation.get("disposition"), str):
        dispositions.append(evaluation["disposition"])
    if isinstance(matrix, dict) and isinstance(matrix.get("disposition"), str):
        dispositions.append(matrix["disposition"])
    dashboard = {
        "report_type": REPORT_TYPE,
        "schema_version": SCHEMA_VERSION,
        "disposition": aggregate_disposition(dispositions),
        "input_dir": str(input_dir) if input_dir else None,
        "paths": {
            "events": str(events_path) if events_path else None,
            "evaluation": str(evaluation_path) if evaluation_path else None,
            "policy_matrix": str(matrix_path) if matrix_path else None,
        },
        "summary": {
            "events": len(events),
            "allow_events": sum(1 for item in dispositions if item == "allow"),
            "review_events": sum(1 for item in dispositions if item == "review"),
            "block_events": sum(1 for item in dispositions if item == "block"),
            "evaluation_score": evaluation.get("score") if isinstance(evaluation, dict) else None,
            "evaluation_checks": len(evaluation.get("checks", [])) if isinstance(evaluation, dict) else 0,
            "policy_scenarios": matrix.get("scenario_count") if isinstance(matrix, dict) else 0,
            "policy_scenarios_passed": matrix.get("passed_scenarios") if isinstance(matrix, dict) else 0,
        },
        "events": events,
        "evaluation": evaluation,
        "policy_matrix": matrix,
    }
    return dashboard


def aggregate_disposition(dispositions: list[str]) -> str:
    if any(item == "block" for item in dispositions):
        return "block"
    if any(item == "review" for item in dispositions):
        return "review"
    return "allow"


def load_json(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    events = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        if isinstance(data, dict):
            events.append(data)
    return events


def _optional_path(input_dir: Path | None, filename: str) -> Path | None:
    return input_dir / filename if input_dir else None


def render_html(dashboard: dict[str, Any]) -> str:
    summary = dashboard["summary"]
    events = dashboard["events"]
    evaluation = dashboard["evaluation"] if isinstance(dashboard.get("evaluation"), dict) else {}
    matrix = dashboard["policy_matrix"] if isinstance(dashboard.get("policy_matrix"), dict) else {}
    return "\n".join(
        [
            "<!doctype html>",
            '<html lang="en">',
            "<head>",
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            "<title>Agent Handoff Observability</title>",
            "<style>",
            CSS,
            "</style>",
            "</head>",
            "<body>",
            '<main class="shell">',
            "<header>",
            "<p>Agent Capsule</p>",
            "<h1>Agent Handoff Observability</h1>",
            f'<span class="badge {css_class(dashboard["disposition"])}">{escape(dashboard["disposition"])}</span>',
            "</header>",
            '<section class="metrics">',
            metric("Events", summary["events"]),
            metric("Evaluation Score", _value_or_dash(summary["evaluation_score"])),
            metric("Policy Scenarios", _scenario_metric(summary)),
            metric("Blocks", summary["block_events"]),
            "</section>",
            '<section class="panel">',
            "<h2>Receiver Evidence</h2>",
            render_evaluation(evaluation),
            "</section>",
            '<section class="panel">',
            "<h2>Policy Matrix</h2>",
            render_matrix(matrix),
            "</section>",
            '<section class="panel">',
            "<h2>Event Timeline</h2>",
            render_events(events),
            "</section>",
            '<section class="panel">',
            "<h2>Artifact Paths</h2>",
            render_paths(dashboard["paths"]),
            "</section>",
            "</main>",
            "</body>",
            "</html>",
        ]
    )


def metric(label: str, value: object) -> str:
    return f'<div class="metric"><span>{escape(label)}</span><strong>{escape(value)}</strong></div>'


def _value_or_dash(value: object) -> object:
    return "-" if value is None else value


def _scenario_metric(summary: dict[str, Any]) -> str:
    total = summary.get("policy_scenarios")
    passed = summary.get("policy_scenarios_passed")
    if total in {None, 0}:
        return "-"
    return f"{passed}/{total}"


def render_evaluation(evaluation: dict[str, Any]) -> str:
    checks = evaluation.get("checks", [])
    if not isinstance(checks, list) or not checks:
        return '<p class="muted">No evaluation report was provided.</p>'
    rows = []
    for check in checks:
        if not isinstance(check, dict):
            continue
        rows.append(
            "<tr>"
            f"<td>{escape(check.get('id'))}</td>"
            f'<td><span class="badge {css_class(check.get("status"))}">{escape(check.get("status"))}</span></td>'
            f"<td>{escape(check.get('severity'))}</td>"
            f"<td>{escape(check.get('message'))}</td>"
            "</tr>"
        )
    return table(["Check", "Status", "Severity", "Message"], rows)


def render_matrix(matrix: dict[str, Any]) -> str:
    scenarios = matrix.get("scenarios", [])
    if not isinstance(scenarios, list) or not scenarios:
        return '<p class="muted">No policy matrix report was provided.</p>'
    rows = []
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        status = "pass" if scenario.get("passed") else "fail"
        rows.append(
            "<tr>"
            f"<td>{escape(scenario.get('name'))}</td>"
            f"<td>{escape(scenario.get('operation'))}</td>"
            f"<td>{escape(scenario.get('expected_disposition'))}</td>"
            f"<td>{escape(scenario.get('observed_disposition'))}</td>"
            f'<td><span class="badge {css_class(status)}">{escape(status)}</span></td>'
            "</tr>"
        )
    return table(["Scenario", "Operation", "Expected", "Observed", "Result"], rows)


def render_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return '<p class="muted">No events were provided.</p>'
    rows = []
    for index, event in enumerate(events, start=1):
        operation = event.get("step") or event.get("operation") or event.get("event_type")
        rows.append(
            "<tr>"
            f"<td>{index}</td>"
            f"<td>{escape(operation)}</td>"
            f'<td><span class="badge {css_class(event.get("disposition"))}">{escape(event.get("disposition"))}</span></td>'
            f"<td>{escape(_event_detail(event))}</td>"
            "</tr>"
        )
    return table(["#", "Operation", "Disposition", "Evidence"], rows)


def _event_detail(event: dict[str, Any]) -> str:
    result = event.get("result")
    if isinstance(result, dict):
        if result.get("verification"):
            return f"verification={result.get('verification')}"
        if result.get("risk_level"):
            return f"risk={result.get('risk_level')} valid_capsules={result.get('valid_capsules')}"
        if result.get("match") is not None:
            return f"match={result.get('match')}"
    return str(event.get("subject") or event.get("report_type") or "")


def render_paths(paths: dict[str, Any]) -> str:
    rows = []
    for label, path in paths.items():
        rows.append("<tr>" f"<td>{escape(label)}</td>" f"<td><code>{escape(path or '-')}</code></td>" "</tr>")
    return table(["Artifact", "Path"], rows)


def table(headers: list[str], rows: list[str]) -> str:
    header_html = "".join(f"<th>{escape(header)}</th>" for header in headers)
    return "<table><thead><tr>" + header_html + "</tr></thead><tbody>" + "".join(rows) + "</tbody></table>"


def css_class(value: object) -> str:
    text = str(value)
    if text in {"allow", "pass", "ok", "trusted"}:
        return "ok"
    if text in {"review", "warn", "medium"}:
        return "review"
    if text in {"block", "fail", "failed", "high"}:
        return "block"
    return "neutral"


def escape(value: object) -> str:
    return html.escape("" if value is None else str(value))


CSS = """
:root {
  color-scheme: light;
  --bg: #f7f8fa;
  --panel: #ffffff;
  --text: #18202a;
  --muted: #5e6b7a;
  --line: #d9dee7;
  --ok: #0f7a4f;
  --ok-bg: #dff4e9;
  --review: #8a5a00;
  --review-bg: #fff0c2;
  --block: #a12b2b;
  --block-bg: #ffe1df;
  --neutral-bg: #eef1f5;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
.shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 28px 0 40px;
}
header {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px 20px;
  align-items: end;
  padding-bottom: 18px;
}
header p {
  margin: 0;
  color: var(--muted);
  font-size: 13px;
}
h1 {
  margin: 0;
  font-size: 28px;
  font-weight: 700;
  letter-spacing: 0;
}
h2 {
  margin: 0 0 14px;
  font-size: 17px;
  letter-spacing: 0;
}
.metrics {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-bottom: 12px;
}
.metric, .panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
}
.metric {
  padding: 14px;
  min-height: 84px;
}
.metric span {
  display: block;
  color: var(--muted);
  font-size: 12px;
}
.metric strong {
  display: block;
  margin-top: 8px;
  font-size: 26px;
}
.panel {
  padding: 16px;
  margin-top: 12px;
  overflow-x: auto;
}
.badge {
  display: inline-flex;
  align-items: center;
  min-height: 24px;
  padding: 2px 9px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 650;
  white-space: nowrap;
}
.badge.ok { background: var(--ok-bg); color: var(--ok); }
.badge.review { background: var(--review-bg); color: var(--review); }
.badge.block { background: var(--block-bg); color: var(--block); }
.badge.neutral { background: var(--neutral-bg); color: var(--muted); }
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  padding: 10px 8px;
  border-top: 1px solid var(--line);
  text-align: left;
  vertical-align: top;
}
th {
  color: var(--muted);
  font-size: 12px;
  font-weight: 650;
}
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  overflow-wrap: anywhere;
}
.muted {
  color: var(--muted);
}
@media (max-width: 760px) {
  .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  header { grid-template-columns: 1fr; }
}
""".strip()


if __name__ == "__main__":
    raise SystemExit(main())

