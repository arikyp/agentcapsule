import math
import unittest

from lmcodec.quantizer import DEFAULT_TOTAL, quantize


class QuantizerStressTests(unittest.TestCase):
    def test_quantizer_invariants_hold_for_representative_distributions(self) -> None:
        distributions = [
            [1.0] * 64,
            [1_000_000.0] + [1.0] * 63,
            [1.0] + [1e-300] * 63,
            [math.nan, math.inf, -1.0, 0.0, 0.5, 2.0],
            [0.0] * 64,
        ]

        for probs in distributions:
            with self.subTest(vocab_size=len(probs), first=probs[0]):
                q = quantize(probs)

                self.assertEqual(sum(q.frequencies), DEFAULT_TOTAL)
                self.assertEqual(q.cdf[0], 0)
                self.assertEqual(q.cdf[-1], DEFAULT_TOTAL)
                self.assertTrue(all(left < right for left, right in zip(q.cdf, q.cdf[1:])))
                self.assertTrue(all(freq >= 1 for freq in q.frequencies))

    def test_all_zero_probabilities_fall_back_to_uniform_distribution(self) -> None:
        q = quantize([0.0] * 8)

        self.assertEqual(q.frequencies, (8192,) * 8)
        self.assertEqual(q.cdf[-1], DEFAULT_TOTAL)

    def test_equal_remainders_are_assigned_by_token_id_order(self) -> None:
        q = quantize([1.0] * 10)

        self.assertEqual(q.frequencies[:6], (6554,) * 6)
        self.assertEqual(q.frequencies[6:], (6553,) * 4)
        self.assertEqual(q, quantize([1.0] * 10))

    def test_invalid_float_inputs_are_cleaned_deterministically(self) -> None:
        probs = [math.nan, math.inf, -7.0, 0.0, 1.0]

        self.assertEqual(quantize(probs), quantize(probs))
        self.assertEqual(quantize(probs).frequencies[:4], (1, 1, 1, 1))
        self.assertEqual(sum(quantize(probs).frequencies), DEFAULT_TOTAL)


if __name__ == "__main__":
    unittest.main()
