import unittest

from scripts.sweep_shaping import _float_list, preview_diversity


class SweepShapingTests(unittest.TestCase):
    def test_float_list_parses_comma_values(self) -> None:
        self.assertEqual(_float_list("0.75, 1.0,2"), [0.75, 1.0, 2.0])

    def test_preview_diversity_penalizes_repetition(self) -> None:
        self.assertLess(preview_diversity("aaaaaaaaaa"), preview_diversity("abcdefghi"))


if __name__ == "__main__":
    unittest.main()
