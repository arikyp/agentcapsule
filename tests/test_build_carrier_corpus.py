import unittest

from lmcodec.lm import default_vocab
from scripts.build_carrier_corpus import SEED_LINES, build_lines, corpus_report


class BuildCarrierCorpusTests(unittest.TestCase):
    def test_build_lines_is_deterministic(self) -> None:
        self.assertEqual(build_lines(20, seed=7), build_lines(20, seed=7))

    def test_build_lines_keeps_seed_content_and_vocab(self) -> None:
        lines = build_lines(40, seed=42)
        text = "\n".join(lines) + "\n"

        self.assertEqual(len(lines), 40)
        self.assertTrue(set(SEED_LINES).issubset(set(lines)))
        self.assertFalse(set(text) - set(default_vocab()) - {"\n"})
        self.assertGreater(len(set(lines)), 30)

    def test_domain_generation_is_deterministic_and_reported(self) -> None:
        lines = build_lines(24, seed=11, domain="operations")
        self.assertEqual(lines, build_lines(24, seed=11, domain="operations"))

        report = corpus_report("\n".join(lines) + "\n", domain="operations", seed=11)
        self.assertEqual(report["domain"], "operations")
        self.assertEqual(report["seed"], 11)
        self.assertEqual(report["invalid_chars"], [])
        self.assertGreater(report["unique_chars"], 10)


if __name__ == "__main__":
    unittest.main()
