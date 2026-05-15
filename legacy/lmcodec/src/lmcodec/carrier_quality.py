"""Carrier text quality metrics that do not affect codec correctness."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class CarrierQualityMetrics:
    unique_character_count: int
    character_frequency: dict[str, int]
    longest_repeated_run: int
    preview_sample: str
    char_frequency_l1_divergence: float | None = None
    char_frequency_kl_bits: float | None = None


def carrier_quality_metrics(
    carrier_text: str,
    *,
    reference_text: str | None = None,
    preview_chars: int = 80,
) -> CarrierQualityMetrics:
    counts = Counter(carrier_text)
    reference_counts = Counter(reference_text) if reference_text is not None else None
    l1 = None
    kl_bits = None
    if reference_counts is not None:
        l1 = _l1_divergence(counts, reference_counts)
        kl_bits = _smoothed_kl_bits(counts, reference_counts)
    return CarrierQualityMetrics(
        unique_character_count=len(counts),
        character_frequency={char: counts[char] for char in sorted(counts)},
        longest_repeated_run=longest_repeated_run(carrier_text),
        preview_sample=carrier_text[:preview_chars],
        char_frequency_l1_divergence=l1,
        char_frequency_kl_bits=kl_bits,
    )


def longest_repeated_run(text: str) -> int:
    longest = 0
    current = 0
    previous = None
    for char in text:
        if char == previous:
            current += 1
        else:
            previous = char
            current = 1
        longest = max(longest, current)
    return longest


def _l1_divergence(left: Counter[str], right: Counter[str]) -> float:
    alphabet = set(left) | set(right)
    left_total = sum(left.values())
    right_total = sum(right.values())
    if left_total == 0 and right_total == 0:
        return 0.0
    if left_total == 0 or right_total == 0:
        return 2.0
    return sum(abs(left[char] / left_total - right[char] / right_total) for char in alphabet)


def _smoothed_kl_bits(left: Counter[str], right: Counter[str]) -> float:
    alphabet = sorted(set(left) | set(right))
    if not alphabet:
        return 0.0
    left_total = sum(left.values()) + len(alphabet)
    right_total = sum(right.values()) + len(alphabet)
    total = 0.0
    for char in alphabet:
        p = (left[char] + 1.0) / left_total
        q = (right[char] + 1.0) / right_total
        total += p * math.log2(p / q)
    return total
