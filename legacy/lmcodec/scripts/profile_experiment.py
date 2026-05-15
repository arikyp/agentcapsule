#!/usr/bin/env python3
"""Profile one LMCodec experiment config."""

from __future__ import annotations

import argparse
import cProfile
import io
import pstats
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from scripts import run_experiment  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", help="experiment JSON config")
    parser.add_argument("--sort", default="cumtime", help="pstats sort key")
    parser.add_argument("--limit", type=int, default=40, help="number of rows to print")
    parser.add_argument("--profile-out", help="optional raw cProfile output path")
    args = parser.parse_args(argv)

    profiler = cProfile.Profile()
    code = profiler.runcall(run_experiment.main, [args.config])
    if args.profile_out:
        profiler.dump_stats(args.profile_out)

    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs().sort_stats(args.sort)
    stats.print_stats(args.limit)
    print(stream.getvalue())
    return code


if __name__ == "__main__":
    raise SystemExit(main())
