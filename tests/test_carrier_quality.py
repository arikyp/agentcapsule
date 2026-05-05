import unittest
from collections import Counter

from lmcodec.carrier_quality import carrier_quality_metrics, longest_repeated_run


class CarrierQualityTests(unittest.TestCase):
    def test_carrier_quality_reports_diversity_and_reference_divergence(self) -> None:
        metrics = carrier_quality_metrics("aaabbc", reference_text="abcabc", preview_chars=4)

        self.assertEqual(metrics.unique_character_count, 3)
        self.assertEqual(metrics.character_frequency, {"a": 3, "b": 2, "c": 1})
        self.assertEqual(metrics.longest_repeated_run, 3)
        self.assertEqual(metrics.preview_sample, "aaab")
        self.assertIsNotNone(metrics.char_frequency_l1_divergence)
        self.assertIsNotNone(metrics.char_frequency_kl_bits)
        self.assertGreater(metrics.char_frequency_l1_divergence, 0.0)

    def test_longest_repeated_run_handles_empty_and_mixed_text(self) -> None:
        self.assertEqual(longest_repeated_run(""), 0)
        self.assertEqual(longest_repeated_run("abcccdd"), 3)

    def test_character_frequency_matches_counter_order_independent_counts(self) -> None:
        text = "cbaabc"
        metrics = carrier_quality_metrics(text)

        self.assertEqual(metrics.character_frequency, dict(sorted(Counter(text).items())))


if __name__ == "__main__":
    unittest.main()
