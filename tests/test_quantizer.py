import unittest

from lmcodec.quantizer import DEFAULT_TOTAL, quantize


class QuantizerTests(unittest.TestCase):
    def test_invariants(self) -> None:
        q = quantize([0.7, 0.2, 0.1])

        self.assertEqual(sum(q.frequencies), DEFAULT_TOTAL)
        self.assertTrue(all(freq >= 1 for freq in q.frequencies))
        self.assertEqual(q.cdf[0], 0)
        self.assertEqual(q.cdf[-1], DEFAULT_TOTAL)
        self.assertEqual(len(q.cdf), 4)

    def test_deterministic_ties(self) -> None:
        q1 = quantize([1.0, 1.0, 1.0, 1.0])
        q2 = quantize([1.0, 1.0, 1.0, 1.0])

        self.assertEqual(q1, q2)

    def test_zero_distribution_falls_back_to_uniform(self) -> None:
        q = quantize([0.0, 0.0, 0.0])

        self.assertEqual(sum(q.frequencies), DEFAULT_TOTAL)
        self.assertTrue(all(freq >= 1 for freq in q.frequencies))


if __name__ == "__main__":
    unittest.main()

