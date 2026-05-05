#!/usr/bin/env python3
"""Create deterministic train/held-out carrier corpus splits."""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.lm import default_vocab  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--train-out", required=True)
    parser.add_argument("--heldout-out", required=True)
    parser.add_argument("--heldout-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--min-segment-chars", type=int, default=24)
    parser.add_argument("--filter-vocab", action="store_true")
    parser.add_argument("--report-json", help="write split validation and vocabulary report")
    args = parser.parse_args(argv)

    if not 0.0 < args.heldout_ratio < 1.0:
        print("heldout-ratio must be between 0 and 1", file=sys.stderr)
        return 2
    if args.min_segment_chars <= 0:
        print("min-segment-chars must be positive", file=sys.stderr)
        return 2

    text = Path(args.input).read_text(encoding="utf-8")
    before_filter = text
    if args.filter_vocab:
        allowed = set(default_vocab())
        text = "".join(char for char in text if char in allowed or char in "\r\n")
    segments = _segments(text, min_chars=args.min_segment_chars)
    if len(segments) < 2:
        print("input corpus must contain at least two usable segments", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    rng.shuffle(segments)
    heldout_count = max(1, min(len(segments) - 1, round(len(segments) * args.heldout_ratio)))
    heldout = segments[:heldout_count]
    train = segments[heldout_count:]

    _write_segments(Path(args.train_out), train)
    _write_segments(Path(args.heldout_out), heldout)
    if args.report_json:
        Path(args.report_json).write_text(
            json.dumps(
                split_report(
                    before_filter,
                    text,
                    train,
                    heldout,
                    filter_vocab=args.filter_vocab,
                    heldout_ratio=args.heldout_ratio,
                    seed=args.seed,
                ),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    print(f"segments: {len(segments)}")
    print(f"train segments: {len(train)}")
    print(f"heldout segments: {len(heldout)}")
    print(f"train chars: {sum(len(item) for item in train)}")
    print(f"heldout chars: {sum(len(item) for item in heldout)}")
    return 0


def _segments(text: str, *, min_chars: int) -> list[str]:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    chunks: list[str] = []
    pending: list[str] = []
    pending_chars = 0
    for raw in normalized.split("\n"):
        line = raw.strip()
        if not line:
            continue
        pending.append(line)
        pending_chars += len(line)
        if pending_chars >= min_chars:
            chunks.append(" ".join(pending))
            pending = []
            pending_chars = 0
    if pending:
        tail = " ".join(pending)
        if chunks and len(tail) < min_chars:
            chunks[-1] = chunks[-1] + " " + tail
        else:
            chunks.append(tail)
    return chunks


def _write_segments(path: Path, segments: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(segments) + "\n", encoding="utf-8", newline="\n")


def split_report(
    original_text: str,
    filtered_text: str,
    train: list[str],
    heldout: list[str],
    *,
    filter_vocab: bool,
    heldout_ratio: float,
    seed: int,
) -> dict[str, object]:
    allowed = set(default_vocab()) | {"\n", "\r"}
    original_invalid = sorted(set(original_text) - allowed)
    filtered_invalid = sorted(set(filtered_text) - allowed)
    train_text = "\n".join(train)
    heldout_text = "\n".join(heldout)
    train_counts = Counter(train_text)
    heldout_counts = Counter(heldout_text)
    return {
        "seed": seed,
        "heldout_ratio": heldout_ratio,
        "filter_vocab": filter_vocab,
        "segments": len(train) + len(heldout),
        "train_segments": len(train),
        "heldout_segments": len(heldout),
        "train_chars": sum(len(item) for item in train),
        "heldout_chars": sum(len(item) for item in heldout),
        "original_invalid_chars": original_invalid,
        "filtered_invalid_chars": filtered_invalid,
        "train_unique_chars": len(train_counts),
        "heldout_unique_chars": len(heldout_counts),
        "shared_unique_chars": len(set(train_counts) & set(heldout_counts)),
    }


if __name__ == "__main__":
    raise SystemExit(main())
