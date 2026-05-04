"""Deterministic probability quantization."""

from __future__ import annotations

from dataclasses import dataclass
from math import floor, isfinite

DEFAULT_TOTAL = 65536


@dataclass(frozen=True)
class QuantizedDistribution:
    frequencies: tuple[int, ...]
    cdf: tuple[int, ...]
    total: int


def quantize(probs: list[float] | tuple[float, ...], *, total: int = DEFAULT_TOTAL) -> QuantizedDistribution:
    """Convert probabilities to an integer CDF.

    All tokens are active in V1. Frequencies are deterministic and every token
    receives at least one count.
    """

    if total <= 0:
        raise ValueError("total must be positive")
    if not probs:
        raise ValueError("probs must not be empty")
    if len(probs) > total:
        raise ValueError("vocabulary size cannot exceed total")

    cleaned = [p if isfinite(p) and p > 0.0 else 0.0 for p in probs]
    prob_sum = sum(cleaned)
    if prob_sum <= 0.0:
        cleaned = [1.0 / len(probs)] * len(probs)
    else:
        cleaned = [p / prob_sum for p in cleaned]

    scaled = [p * total for p in cleaned]
    floors = [floor(x) for x in scaled]
    remainders = [x - base for x, base in zip(scaled, floors, strict=True)]
    frequencies = [max(1, int(base)) for base in floors]

    delta = total - sum(frequencies)
    if delta > 0:
        order = sorted(range(len(frequencies)), key=lambda i: (-remainders[i], i))
        idx = 0
        while delta:
            frequencies[order[idx % len(order)]] += 1
            delta -= 1
            idx += 1
    elif delta < 0:
        order = sorted(range(len(frequencies)), key=lambda i: (remainders[i], i))
        remaining = -delta
        while remaining:
            changed = False
            for token_id in order:
                if frequencies[token_id] > 1:
                    frequencies[token_id] -= 1
                    remaining -= 1
                    changed = True
                    if remaining == 0:
                        break
            if not changed:
                raise ValueError("cannot reduce frequencies to requested total")

    cdf = [0]
    running = 0
    for freq in frequencies:
        running += freq
        cdf.append(running)

    if running != total:
        raise AssertionError("quantizer failed to hit total")
    return QuantizedDistribution(tuple(frequencies), tuple(cdf), total)

