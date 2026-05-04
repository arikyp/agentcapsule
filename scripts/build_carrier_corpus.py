#!/usr/bin/env python3
"""Build a deterministic synthetic carrier-text corpus."""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from lmcodec.lm import default_vocab  # noqa: E402


NOUNS = [
    "message",
    "payload",
    "packet",
    "archive",
    "document",
    "notebook",
    "ledger",
    "report",
    "memo",
    "transcript",
    "stream",
    "frame",
    "block",
    "window",
    "buffer",
    "channel",
    "terminal",
    "console",
    "session",
    "record",
    "summary",
    "draft",
    "entry",
    "queue",
    "bundle",
    "snapshot",
    "artifact",
    "token",
    "symbol",
    "receipt",
]

VERBS = [
    "carries",
    "preserves",
    "checks",
    "copies",
    "wraps",
    "stores",
    "moves",
    "routes",
    "verifies",
    "streams",
    "mirrors",
    "guards",
    "tracks",
    "prints",
    "reads",
    "writes",
    "shapes",
    "counts",
    "tests",
    "recovers",
    "balances",
    "compares",
    "explains",
    "describes",
    "signals",
    "reports",
    "marks",
    "loads",
    "saves",
]

ACTIONS = [
    "carry",
    "preserve",
    "check",
    "copy",
    "wrap",
    "store",
    "move",
    "route",
    "verify",
    "stream",
    "mirror",
    "guard",
    "track",
    "print",
    "read",
    "write",
    "shape",
    "count",
    "test",
    "recover",
    "balance",
    "compare",
    "explain",
    "describe",
    "signal",
    "report",
    "mark",
    "load",
    "save",
]

ADJECTIVES = [
    "small",
    "clear",
    "stable",
    "plain",
    "quiet",
    "careful",
    "exact",
    "lossless",
    "portable",
    "deterministic",
    "encoded",
    "decoded",
    "binary",
    "textual",
    "sampled",
    "trained",
    "heldout",
    "golden",
    "safe",
    "repeatable",
    "ordinary",
    "readable",
    "measured",
    "useful",
    "direct",
    "simple",
    "local",
    "warm",
    "neutral",
]

PLACES = [
    "chat window",
    "mail draft",
    "system log",
    "field note",
    "terminal pane",
    "issue report",
    "release note",
    "debug trace",
    "status page",
    "copy buffer",
    "shell history",
    "plain file",
    "review comment",
    "test output",
    "build log",
    "daily note",
    "project journal",
    "operator memo",
    "lab notebook",
    "work queue",
    "handoff note",
    "audit trail",
    "packet journal",
    "archive index",
]

TOPICS = [
    "range coder",
    "language model",
    "carrier alphabet",
    "checksum field",
    "model fingerprint",
    "golden fixture",
    "heldout split",
    "training corpus",
    "entropy guard",
    "probability shape",
    "copy paste path",
    "binary frame",
    "payload length",
    "decode state",
    "encode mirror",
    "quality metric",
    "training note",
    "text preview",
    "roundtrip check",
    "symbol stream",
    "model export",
    "cpu trainer",
    "corpus builder",
    "research loop",
]

TEMPLATES = [
    "the {adj} {noun} {verb} through the {place}",
    "the {topic} keeps the {noun} {adj} during transport",
    "engineers {action} the {adj} {noun} before release {num}",
    "the {place} shows the {adj} {topic} for case {num}",
    "every {noun} needs the {adj} checksum and a repeatable model",
    "the codec turns bytes into {adj} text with style {num}",
    "heldout readers compare {topic} results across run {num}",
    "the {adj} carrier avoids surprises in the {place}",
    "the {topic} {verb} symbols while the payload stays exact",
    "test case {num} stores the {adj} {noun} in ordinary text",
    "during run {num} the {place} records the {adj} {topic}",
    "the {noun} stays {adj} because the {topic} {verb} each step",
    "operators use the {place} to {action} the {adj} {noun}",
    "the {adj} {topic} makes the {noun} easy to compare",
    "readers can follow the {adj} {noun} without seeing the bytes",
    "run {num} reports the {topic} and saves the {adj} {noun}",
    "the {place} contains the {adj} {noun} for later review",
    "each {topic} gives the {noun} a stable path across text",
    "the {adj} {noun} describes how the {topic} changed today",
    "when the {noun} moves the {topic} keeps the carrier readable",
]

SEED_LINES = [
    "the language modem carries bytes through ordinary looking text",
    "small messages move through notes memos logs and chat windows",
    "the carrier prefers letters spaces numbers and calm punctuation",
    "every decoded payload must match the original byte stream exactly",
    "range coding maps bits into symbols while the model shapes style",
    "deterministic fixtures make drift visible before it reaches users",
    "copy paste transport needs clear markers checksums and versions",
    "engineers test empty files tiny files and larger binary payloads",
    "the quick brown fox jumps over the lazy dog 0123456789",
    "alpha beta gamma delta epsilon zeta eta theta iota kappa",
    "model shaped text is only the envelope the payload remains exact",
    "lossless transport matters more than pretty prose in this version",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--lines", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    if args.lines < len(SEED_LINES):
        print(f"lines must be at least {len(SEED_LINES)}", file=sys.stderr)
        return 2

    lines = build_lines(args.lines, seed=args.seed)
    text = "\n".join(lines) + "\n"
    invalid = sorted(set(text) - set(default_vocab()) - {"\n"})
    if invalid:
        print(f"generated corpus contains invalid chars: {invalid!r}", file=sys.stderr)
        return 2

    Path(args.out).write_text(text, encoding="utf-8", newline="\n")
    print(f"lines: {len(lines)}")
    print(f"chars: {len(text)}")
    print(f"path: {args.out}")
    return 0


def build_lines(count: int, *, seed: int) -> list[str]:
    rng = random.Random(seed)
    lines = list(SEED_LINES)
    for idx in range(count - len(lines)):
        template = TEMPLATES[idx % len(TEMPLATES)]
        line = template.format(
            adj=rng.choice(ADJECTIVES),
            noun=rng.choice(NOUNS),
            verb=rng.choice(VERBS),
            action=rng.choice(ACTIONS),
            place=rng.choice(PLACES),
            topic=rng.choice(TOPICS),
            num=f"{idx % 1000:03d}",
        )
        lines.append(line)
    rng.shuffle(lines)
    return lines


if __name__ == "__main__":
    raise SystemExit(main())
