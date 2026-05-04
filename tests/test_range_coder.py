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


if __name__ == "__main__":
    unittest.main()

