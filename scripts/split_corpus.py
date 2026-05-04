#!/usr/bin/env python3
"""Create deterministic train/held-out carrier corpus splits."""

from __future__ import annotations

import argparse
import random
import sys
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
    args = parser.parse_args(argv)

    if not 0.0 < args.heldout_ratio < 1.0:
        print("heldout-ratio must be between 0 and 1", file=sys.stderr)
        return 2
    if args.min_segment_chars <= 0:
        print("min-segment-chars must be positive", file=sys.stderr)
        return 2

    text = Path(args.input).read_text(encoding="utf-8")
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


if __name__ == "__main__":
    raise SystemExit(main())
