import unittest

from lmcodec.range_coder import RangeDecoder, RangeEncoder


class RangeCoderTests(unittest.TestCase):
    def test_roundtrip_fixed_distribution(self) -> None:
        cdf = (0, 1, 3, 7, 16)
        symbols = [0, 1, 2, 3, 3, 2, 1, 0, 3, 0, 2]

        encoder = RangeEncoder()
        for symbol in symbols:
            encoder.push_symbol(cdf, symbol)
        bits = encoder.finish()

        decoder = RangeDecoder(bits)
        decoded = [decoder.pop_symbol(cdf) for _ in symbols]

        self.assertEqual(decoded, symbols)

    def test_roundtrip_changing_distribution(self) -> None:
        cdfs = [
            (0, 1, 2),
            (0, 5, 8),
            (0, 2, 9),
            (0, 1, 100),
            (0, 99, 100),
        ]
        symbols = [0, 1, 1, 1, 0]

        encoder = RangeEncoder()
        for cdf, symbol in zip(cdfs, symbols, strict=True):
            encoder.push_symbol(cdf, symbol)
        bits = encoder.finish()

        decoder = RangeDecoder(bits)
        decoded = [decoder.pop_symbol(cdf) for cdf in cdfs]

        self.assertEqual(decoded, symbols)

    def test_prefix_helpers_match_materialized_bits(self) -> None:
        cdf = (0, 1, 3, 7, 16)
        encoder = RangeEncoder()
        target = [0, 1, 0, 1, 1, 0]

        for symbol in [0, 1, 2, 3, 1]:
            encoder.push_symbol(cdf, symbol)
            emitted = encoder.bits
            self.assertEqual(encoder.bits_prefix(len(emitted)), emitted)
            checked = min(len(emitted), len(target))
            self.assertEqual(
                encoder.emitted_prefix_matches(target),
                list(emitted[:checked]) == target[:checked],
            )
            self.assertEqual(
                encoder.emitted_prefix_matches_from(target, max(0, checked - 1)),
                list(emitted[max(0, checked - 1) : checked])
                == target[max(0, checked - 1) : checked],
            )

        finished = encoder.preview_finish()
        emitted = encoder.bits
        self.assertTrue(encoder.emitted_prefix_matches(list(finished)))

        for length in range(len(emitted), len(finished) + 1):
            target_prefix = list(finished[:length])
            self.assertEqual(
                encoder.preview_finish_extends_prefix(target_prefix),
                len(finished) >= length and list(finished[:length]) == target_prefix,
            )
        self.assertFalse(encoder.preview_finish_extends_prefix(list(finished) + [0]))

        if len(finished) > len(emitted):
            mismatched_prefix = list(finished[: len(emitted) + 1])
            mismatched_prefix[-1] = 1 - mismatched_prefix[-1]
            self.assertFalse(encoder.preview_finish_extends_prefix(mismatched_prefix))


if __name__ == "__main__":
    unittest.main()
