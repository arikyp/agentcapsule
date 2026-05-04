import unittest

from lmcodec.codec import CodecSettings
from lmcodec.experiments import build_probability_trace, evaluate_quality, evaluate_quality_trace, greedy_preview, measure_roundtrip
from lmcodec.lm import FixedLM
from lmcodec.probability import ProbabilityShapeSettings


class ExperimentHarnessTests(unittest.TestCase):
    def test_measure_roundtrip_reports_metrics(self) -> None:
        metrics = measure_roundtrip("fixed", b"payload", FixedLM())

        self.assertEqual(metrics.name, "fixed")
        self.assertEqual(metrics.payload_bytes, 7)
        self.assertGreater(metrics.carrier_chars, 0)
        self.assertTrue(metrics.carrier_preview)
        self.assertGreater(metrics.bits_per_carrier_char, 0.0)

    def test_evaluate_quality_reports_language_metrics(self) -> None:
        metrics = evaluate_quality(FixedLM(), "abc abc", preview_chars=12)

        self.assertEqual(metrics.token_count, 7)
        self.assertAlmostEqual(metrics.avg_nll_bits, 6.0)
        self.assertAlmostEqual(metrics.avg_entropy_bits, 6.0)
        self.assertAlmostEqual(metrics.avg_top_probability, 1.0 / 64.0)
        self.assertEqual(len(metrics.greedy_preview), 12)

    def test_measure_roundtrip_can_include_quality_metrics(self) -> None:
        metrics = measure_roundtrip("fixed", b"payload", FixedLM(), quality_text="abc")

        self.assertIsNotNone(metrics.quality)
        assert metrics.quality is not None
        self.assertEqual(metrics.quality.token_count, 3)

    def test_greedy_preview_is_deterministic(self) -> None:
        model = FixedLM()

        self.assertEqual(greedy_preview(model, max_chars=8), greedy_preview(model, max_chars=8))

    def test_probability_trace_matches_direct_quality_eval(self) -> None:
        model = FixedLM()
        settings = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.25, temperature=1.5))
        direct = evaluate_quality(model, "abc abc", settings=settings, preview_chars=0)
        trace = build_probability_trace(model, "abc abc")
        traced = evaluate_quality_trace(trace, settings=settings)

        self.assertEqual(traced.token_count, direct.token_count)
        self.assertAlmostEqual(traced.avg_nll_bits, direct.avg_nll_bits)
        self.assertAlmostEqual(traced.avg_entropy_bits, direct.avg_entropy_bits)
        self.assertAlmostEqual(traced.avg_top_probability, direct.avg_top_probability)


if __name__ == "__main__":
    unittest.main()
