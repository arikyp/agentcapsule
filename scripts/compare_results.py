#!/usr/bin/env python3
"""Compare LMCodec experiment result JSON files."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any


FIELDS = [
    "experiment_name",
    "payload_bytes",
    "roundtrip_success",
    "promotion_passed",
    "avg_entropy_bits",
    "heldout_nll_bits",
    "bits_per_carrier_char",
    "carrier_chars",
    "unique_character_count",
    "longest_repeated_run",
    "char_frequency_l1_divergence",
    "char_frequency_kl_bits",
    "avg_top_probability",
    "error_message",
]

NUMERIC_FIELDS = {
    "payload_bytes",
    "avg_entropy_bits",
    "heldout_nll_bits",
    "bits_per_carrier_char",
    "carrier_chars",
    "unique_character_count",
    "longest_repeated_run",
    "char_frequency_l1_divergence",
    "char_frequency_kl_bits",
    "avg_top_probability",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", nargs="+", help="result.json paths")
    parser.add_argument("--format", choices=("markdown", "csv"), default="markdown")
    parser.add_argument("--sort", choices=FIELDS, default="heldout_nll_bits")
    parser.add_argument("--baseline", help="result.json path used for numeric deltas")
    parser.add_argument("--json-out", help="write flattened comparison records")
    args = parser.parse_args(argv)

    records = [_record(Path(path)) for path in args.results]
    baseline = _record(Path(args.baseline)) if args.baseline else None
    if baseline is not None:
        records = [_with_deltas(record, baseline) for record in records]

    records.sort(key=lambda record: _sort_key(record, args.sort))

    output_fields = FIELDS[:]
    if baseline is not None:
        output_fields.extend(f"delta_{field}" for field in sorted(NUMERIC_FIELDS))

    if args.format == "csv":
        _print_csv(records, output_fields)
    else:
        _print_markdown(records, output_fields)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    return 0


def _record(path: Path) -> dict[str, Any]:
    document = json.loads(path.read_text(encoding="utf-8"))
    diversity = document.get("carrier_diversity") or {}
    promotion = document.get("promotion") or {}
    return {
        "path": str(path),
        "experiment_name": document.get("experiment_name"),
        "config_path": document.get("config_path"),
        "payload_bytes": document.get("payload_bytes"),
        "roundtrip_success": document.get("roundtrip_success"),
        "promotion_passed": promotion.get("passed"),
        "avg_entropy_bits": document.get("avg_entropy_bits"),
        "heldout_nll_bits": document.get("heldout_nll_bits"),
        "bits_per_carrier_char": document.get("bits_per_carrier_char"),
        "carrier_chars": document.get("carrier_chars"),
        "unique_character_count": diversity.get("unique_character_count"),
        "longest_repeated_run": diversity.get("longest_repeated_run"),
        "char_frequency_l1_divergence": diversity.get("char_frequency_l1_divergence"),
        "char_frequency_kl_bits": diversity.get("char_frequency_kl_bits"),
        "avg_top_probability": document.get("avg_top_probability"),
        "error_message": document.get("error_message"),
    }


def _with_deltas(record: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    with_deltas = dict(record)
    for field in sorted(NUMERIC_FIELDS):
        value = record.get(field)
        base_value = baseline.get(field)
        with_deltas[f"delta_{field}"] = value - base_value if _is_number(value) and _is_number(base_value) else None
    return with_deltas


def _sort_key(record: dict[str, Any], field: str) -> tuple[int, Any]:
    value = record.get(field)
    return (1, "") if value is None else (0, value)


def _print_csv(records: list[dict[str, Any]], fields: list[str]) -> None:
    writer = csv.DictWriter(sys.stdout, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for record in records:
        writer.writerow({field: _format_value(record.get(field), plain=True) for field in fields})


def _print_markdown(records: list[dict[str, Any]], fields: list[str]) -> None:
    print("| " + " | ".join(fields) + " |")
    print("| " + " | ".join("---" for _ in fields) + " |")
    for record in records:
        print("| " + " | ".join(_format_value(record.get(field)) for field in fields) + " |")


def _format_value(value: Any, *, plain: bool = False) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return f"{value:.3f}"
    text = str(value)
    if plain:
        return text
    return text.replace("|", "\\|")


def _is_number(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


if __name__ == "__main__":
    raise SystemExit(main())
