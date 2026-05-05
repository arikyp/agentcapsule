import random
import unittest

from lmcodec.quantizer import DEFAULT_TOTAL
from lmcodec.range_coder import RangeDecoder, RangeEncoder


SEED = 20260505


class RangeCoderStressTests(unittest.TestCase):
    def test_random_symbol_sequences_roundtrip_with_fixed_random_cdfs(self) -> None:
        rng = random.Random(SEED)

        for vocab_size in (2, 3, 5, 17, 64):
            cdf = _random_cdf(rng, vocab_size)
            symbols = [rng.randrange(vocab_size) for _ in range(300)]

            with self.subTest(vocab_size=vocab_size):
                self.assertEqual(_roundtrip(cdf, symbols), symbols)

    def test_random_symbol_sequences_roundtrip_with_changing_cdf_per_symbol(self) -> None:
        rng = random.Random(SEED + 1)
        cdfs: list[tuple[int, ...]] = []
        symbols: list[int] = []

        for _ in range(250):
            vocab_size = rng.choice((2, 4, 8, 16, 32))
            cdf = _random_cdf(rng, vocab_size)
            cdfs.append(cdf)
            symbols.append(rng.randrange(vocab_size))

        encoder = RangeEncoder()
        for cdf, symbol in zip(cdfs, symbols, strict=True):
            encoder.push_symbol(cdf, symbol)

        decoder = RangeDecoder(encoder.finish())
        decoded = [decoder.pop_symbol(cdf) for cdf in cdfs]

        self.assertEqual(decoded, symbols)

    def test_extremely_skewed_two_symbol_distribution_roundtrips(self) -> None:
        cdf = (0, 1, DEFAULT_TOTAL)
        symbols = [1] * 80 + [0] + [1] * 40 + [0] + [1] * 80

        self.assertEqual(_roundtrip(cdf, symbols), symbols)

    def test_changing_skewed_distributions_roundtrip_rare_symbols(self) -> None:
        cdfs = [
            (0, 1, DEFAULT_TOTAL),
            (0, DEFAULT_TOTAL - 1, DEFAULT_TOTAL),
        ] * 40
        symbols = [idx % 2 for idx in range(len(cdfs))]

        encoder = RangeEncoder()
        for cdf, symbol in zip(cdfs, symbols, strict=True):
            encoder.push_symbol(cdf, symbol)

        decoder = RangeDecoder(encoder.finish())
        decoded = [decoder.pop_symbol(cdf) for cdf in cdfs]

        self.assertEqual(decoded, symbols)


def _roundtrip(cdf: tuple[int, ...], symbols: list[int]) -> list[int]:
    encoder = RangeEncoder()
    for symbol in symbols:
        encoder.push_symbol(cdf, symbol)

    decoder = RangeDecoder(encoder.finish())
    return [decoder.pop_symbol(cdf) for _ in symbols]


def _random_cdf(rng: random.Random, vocab_size: int) -> tuple[int, ...]:
    remaining = DEFAULT_TOTAL - vocab_size
    weights = [rng.randrange(1, 10_000) for _ in range(vocab_size)]
    weight_total = sum(weights)
    freqs = [1 + (remaining * weight // weight_total) for weight in weights]
    leftover = DEFAULT_TOTAL - sum(freqs)
    for token_id in sorted(range(vocab_size), key=lambda idx: (-weights[idx], idx)):
        if leftover == 0:
            break
        freqs[token_id] += 1
        leftover -= 1

    cdf = [0]
    running = 0
    for freq in freqs:
        running += freq
        cdf.append(running)
    if cdf[-1] != DEFAULT_TOTAL:
        raise AssertionError("random CDF construction failed")
    return tuple(cdf)


if __name__ == "__main__":
    unittest.main()
