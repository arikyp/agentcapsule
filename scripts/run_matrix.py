#!/usr/bin/env python3
"""Run a deterministic LMCodec V2 experiment matrix."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from statistics import mean
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.lm import default_vocab  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("matrix", help="matrix JSON spec")
    parser.add_argument("--output-dir", help="override matrix output directory")
    parser.add_argument("--dry-run", action="store_true", help="write generated configs without running experiments")
    args = parser.parse_args(argv)

    matrix_path = Path(args.matrix)
    matrix = json.loads(matrix_path.read_text(encoding="utf-8"))
    output_dir = _resolve_output_dir(matrix, matrix_path, args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    payloads = _materialize_payloads(matrix.get("payloads", []), output_dir / "payloads")
    corpora = _materialize_corpora(matrix.get("corpora", []), output_dir / "corpora")
    configs = _write_configs(matrix, payloads, corpora, output_dir)

    records = []
    if not args.dry_run:
        for item in configs:
            records.append(_run_config(item))

    summary = {
        "schema_version": 1,
        "matrix_name": matrix.get("matrix_name", matrix_path.stem),
        "matrix_path": str(matrix_path),
        "output_dir": str(output_dir),
        "run_golden_tests": bool(matrix.get("run_golden_tests", False)),
        "payloads": payloads,
        "corpora": corpora,
        "configs": configs,
        "records": records,
        "rankings": _candidate_rankings(records),
        "dry_run": args.dry_run,
    }
    summary_path = output_dir / "matrix_result.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _print_summary(summary)
    return 0 if args.dry_run or all(record["hard_gate_passed"] for record in records) else 2


def _resolve_output_dir(matrix: dict[str, Any], matrix_path: Path, override: str | None) -> Path:
    if override:
        return Path(override)
    configured = matrix.get("output_dir")
    if configured:
        path = Path(configured)
        return path if path.is_absolute() else ROOT / path
    return ROOT / "experiments" / "runs" / matrix_path.stem


def _materialize_payloads(payload_specs: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    payloads = []
    for spec in payload_specs:
        name = spec["name"]
        data = _payload_bytes(spec)
        path = output_dir / f"{name}.bin"
        path.write_bytes(data)
        payloads.append(
            {
                "name": name,
                "path": str(path),
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
                "kind": spec.get("kind", "literal"),
            }
        )
    return payloads


def _payload_bytes(spec: dict[str, Any]) -> bytes:
    kind = spec.get("kind", "literal")
    if kind == "empty":
        return b""
    if kind == "text":
        return spec.get("text", "").encode("utf-8")
    if kind == "hex":
        return bytes.fromhex(spec.get("hex", ""))
    if kind == "range":
        start = int(spec.get("start", 0))
        count = int(spec["count"])
        return bytes((start + idx) % 256 for idx in range(count))
    if kind == "repeat":
        token = spec.get("token", "").encode("utf-8")
        return token * int(spec["count"])
    if kind == "text_repeat":
        target_bytes = int(spec["bytes"])
        token = spec.get("token", "lmcodec v2 stress payload line\n").encode("utf-8")
        if not token:
            raise ValueError("text_repeat token must not be empty")
        repeated = token * ((target_bytes // len(token)) + 1)
        return repeated[:target_bytes]
    raise ValueError(f"unsupported payload kind: {kind}")


def _materialize_corpora(corpus_specs: list[dict[str, Any]], output_dir: Path) -> list[dict[str, Any]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    corpora = []
    for spec in corpus_specs:
        name = spec["name"]
        corpus_dir = output_dir / name
        corpus_dir.mkdir(parents=True, exist_ok=True)
        corpus_path = corpus_dir / "corpus.txt"
        train_path = corpus_dir / "train.txt"
        heldout_path = corpus_dir / "heldout.txt"
        corpus_report = corpus_dir / "corpus_report.json"
        split_report = corpus_dir / "split_report.json"
        if spec.get("kind", "synthetic") == "files":
            _write_file_corpus(spec, corpus_path, corpus_report)
        else:
            _run_checked(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "build_carrier_corpus.py"),
                    "--out",
                    str(corpus_path),
                    "--lines",
                    str(int(spec.get("lines", 240))),
                    "--seed",
                    str(int(spec.get("seed", 42))),
                    "--domain",
                    spec["domain"],
                    "--report-json",
                    str(corpus_report),
                ]
            )
        _run_checked(
            [
                sys.executable,
                str(ROOT / "scripts" / "split_corpus.py"),
                "--input",
                str(corpus_path),
                "--train-out",
                str(train_path),
                "--heldout-out",
                str(heldout_path),
                "--heldout-ratio",
                str(float(spec.get("heldout_ratio", 0.2))),
                "--seed",
                str(int(spec.get("split_seed", spec.get("seed", 42)))),
                "--filter-vocab",
                "--report-json",
                str(split_report),
            ]
        )
        corpora.append(
            {
                "name": name,
                "domain": spec.get("domain", name),
                "kind": spec.get("kind", "synthetic"),
                "corpus_path": str(corpus_path),
                "train_path": str(train_path),
                "heldout_path": str(heldout_path),
                "corpus_report": str(corpus_report),
                "split_report": str(split_report),
            }
        )
    return corpora


def _write_configs(
    matrix: dict[str, Any],
    payloads: list[dict[str, Any]],
    corpora: list[dict[str, Any]],
    output_dir: Path,
) -> list[dict[str, Any]]:
    config_dir = output_dir / "configs"
    run_dir = output_dir / "runs"
    config_dir.mkdir(parents=True, exist_ok=True)
    run_dir.mkdir(parents=True, exist_ok=True)
    configs = []
    for candidate in matrix.get("candidates", []):
        for corpus in corpora:
            for payload in payloads:
                experiment_name = f"{matrix.get('matrix_name', 'matrix')}-{candidate['name']}-{corpus['name']}-{payload['name']}"
                config = _candidate_config(matrix, candidate, corpus, payload, run_dir / experiment_name, experiment_name)
                config_path = config_dir / f"{experiment_name}.json"
                config_path.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                configs.append(
                    {
                        "experiment_name": experiment_name,
                        "candidate": candidate["name"],
                        "corpus": corpus["name"],
                        "payload": payload["name"],
                        "config_path": str(config_path),
                        "result_path": str(run_dir / experiment_name / "result.json"),
                    }
                )
    return configs


def _candidate_config(
    matrix: dict[str, Any],
    candidate: dict[str, Any],
    corpus: dict[str, Any],
    payload: dict[str, Any],
    output_dir: Path,
    experiment_name: str,
) -> dict[str, Any]:
    model = copy.deepcopy(candidate["model"])
    if "training" in model:
        model["training"]["corpus_path"] = corpus["train_path"]
    return {
        "experiment_name": experiment_name,
        "payload_path": payload["path"],
        "model": model,
        "shape_settings": copy.deepcopy(candidate.get("shape_settings", {})),
        "max_steps": int(candidate.get("max_steps", matrix.get("max_steps", 100000))),
        "run_golden_tests": bool(matrix.get("run_golden_tests", False)),
        "wrap": int(matrix.get("wrap", 80)),
        "quality_text_path": corpus["heldout_path"],
        "promotion_gate": copy.deepcopy(candidate.get("promotion_gate", {})),
        "output_dir": str(output_dir),
        "export_model": bool(candidate.get("export_model", False)),
    }


def _run_config(item: dict[str, Any]) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_experiment.py"), item["config_path"]],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    result_path = Path(item["result_path"])
    result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else {}
    hard_gate = _hard_gate(result)
    return {
        **item,
        "returncode": completed.returncode,
        "stdout": completed.stdout,
        "hard_gate_passed": hard_gate["passed"],
        "hard_gate_checks": hard_gate["checks"],
        "roundtrip_success": result.get("roundtrip_success"),
        "avg_entropy_bits": result.get("avg_entropy_bits"),
        "heldout_nll_bits": result.get("heldout_nll_bits"),
        "bits_per_carrier_char": result.get("bits_per_carrier_char"),
        "carrier_chars": result.get("carrier_chars"),
        "encode_seconds": result.get("encode_seconds"),
        "decode_seconds": result.get("decode_seconds"),
        "avg_top_probability": result.get("avg_top_probability"),
        "error_message": result.get("error_message"),
    }


def _hard_gate(result: dict[str, Any]) -> dict[str, Any]:
    checks = result.get("promotion", {}).get("checks", {})
    gate_checks = {
        "no_error": result.get("error_message") is None,
        "roundtrip_success": result.get("roundtrip_success") is True,
        "decoded_sha256_matches": checks.get("decoded_sha256_matches") is True,
        "model_fingerprint_stable": result.get("model_fingerprint_stable") is True,
        "entropy_above_minimum": checks.get("entropy_above_minimum") is True,
        "no_convergence_failure": result.get("convergence_failure_count") == 0,
    }
    return {"passed": all(gate_checks.values()), "checks": gate_checks}


def _candidate_rankings(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_candidate: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_candidate.setdefault(record["candidate"], []).append(record)
    rankings = []
    for candidate, items in by_candidate.items():
        hard_gate_failures = sum(1 for item in items if not item["hard_gate_passed"])
        rankings.append(
            {
                "candidate": candidate,
                "runs": len(items),
                "hard_gate_failures": hard_gate_failures,
                "hard_gate_passed": hard_gate_failures == 0,
                "mean_heldout_nll_bits": _mean_present(items, "heldout_nll_bits"),
                "mean_avg_entropy_bits": _mean_present(items, "avg_entropy_bits"),
                "mean_bits_per_carrier_char": _mean_present(items, "bits_per_carrier_char"),
                "mean_encode_seconds": _mean_present(items, "encode_seconds"),
                "mean_decode_seconds": _mean_present(items, "decode_seconds"),
                "mean_avg_top_probability": _mean_present(items, "avg_top_probability"),
            }
        )
    rankings.sort(
        key=lambda item: (
            item["hard_gate_failures"],
            _none_last(item["mean_heldout_nll_bits"]),
            -item["mean_avg_entropy_bits"] if item["mean_avg_entropy_bits"] is not None else 0.0,
        )
    )
    return rankings


def _mean_present(records: list[dict[str, Any]], field: str) -> float | None:
    values = [record[field] for record in records if isinstance(record.get(field), int | float)]
    return mean(values) if values else None


def _none_last(value: Any) -> tuple[int, Any]:
    return (1, 0) if value is None else (0, value)


def _run_checked(command: list[str]) -> None:
    completed = subprocess.run(
        command,
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"command failed: {' '.join(command)}\n{completed.stdout}")


def _write_file_corpus(spec: dict[str, Any], corpus_path: Path, report_path: Path) -> None:
    paths = [_resolve_source_path(path) for path in spec.get("paths", [])]
    if not paths:
        raise ValueError("files corpus requires at least one path")
    allowed = set(default_vocab())
    chunks = []
    source_reports = []
    max_chars = spec.get("max_chars")
    remaining = int(max_chars) if max_chars is not None else None
    for path in paths:
        raw = path.read_text(encoding="utf-8")
        filtered = _filter_text_for_vocab(raw, allowed)
        if remaining is not None:
            if remaining <= 0:
                filtered = ""
            else:
                filtered = filtered[:remaining]
                remaining -= len(filtered)
        chunks.append(filtered)
        source_reports.append(
            {
                "path": str(path),
                "raw_chars": len(raw),
                "filtered_chars": len(filtered),
                "raw_sha256": hashlib.sha256(raw.encode("utf-8")).hexdigest(),
            }
        )
    text = "\n".join(chunk.strip() for chunk in chunks if chunk.strip()) + "\n"
    if not text.strip():
        raise ValueError("files corpus produced no usable text")
    corpus_path.write_text(text, encoding="utf-8", newline="\n")
    counts = Counter(text)
    report_path.write_text(
        json.dumps(
            {
                "kind": "files",
                "name": spec["name"],
                "sources": source_reports,
                "chars": len(text),
                "unique_chars": len(counts),
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _resolve_source_path(value: str) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return ROOT / path


def _filter_text_for_vocab(text: str, allowed: set[str]) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").lower()
    return "".join(char if char in allowed or char == "\n" else " " for char in normalized)


def _print_summary(summary: dict[str, Any]) -> None:
    print(f"matrix: {summary['matrix_name']}")
    print(f"output: {summary['output_dir']}")
    print(f"configs: {len(summary['configs'])}")
    if summary["dry_run"]:
        print("dry run: true")
        return
    for ranking in summary["rankings"]:
        print(
            f"{ranking['candidate']}: hard_gate_failures={ranking['hard_gate_failures']} "
            f"mean_nll={_format_float(ranking['mean_heldout_nll_bits'])} "
            f"mean_entropy={_format_float(ranking['mean_avg_entropy_bits'])} "
            f"mean_encode_s={_format_float(ranking['mean_encode_seconds'])}"
        )


def _format_float(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.3f}"


if __name__ == "__main__":
    raise SystemExit(main())
