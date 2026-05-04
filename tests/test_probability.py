import unittest

from lmcodec.errors import LMCodecError
from lmcodec.probability import ProbabilityShapeSettings, entropy_bits, shape_probabilities


class ProbabilityShapingTests(unittest.TestCase):
    def test_default_shape_normalizes_without_changing_valid_distribution(self) -> None:
        shaped = shape_probabilities((0.25, 0.75))

        self.assertEqual(shaped, (0.25, 0.75))

    def test_uniform_mix_increases_entropy_for_skewed_distribution(self) -> None:
        probs = (0.99, 0.01)
        shaped = shape_probabilities(probs, ProbabilityShapeSettings(uniform_mix=0.5))

        self.assertGreater(entropy_bits(shaped), entropy_bits(probs))
        self.assertAlmostEqual(sum(shaped), 1.0)

    def test_temperature_flattens_when_above_one(self) -> None:
        probs = (0.9, 0.1)
        shaped = shape_probabilities(probs, ProbabilityShapeSettings(temperature=2.0))

        self.assertLess(shaped[0], probs[0])
        self.assertGreater(shaped[1], probs[1])

    def test_min_probability_floor_keeps_all_tokens_active(self) -> None:
        shaped = shape_probabilities((1.0, 0.0, 0.0), ProbabilityShapeSettings(min_probability=0.05))

        self.assertTrue(all(prob > 0.0 for prob in shaped))
        self.assertAlmostEqual(sum(shaped), 1.0)

    def test_entropy_guard_fails_low_entropy_distribution(self) -> None:
        with self.assertRaisesRegex(LMCodecError, "entropy guard"):
            shape_probabilities((0.99, 0.01), ProbabilityShapeSettings(min_entropy_bits=0.5))


if __name__ == "__main__":
    unittest.main()
