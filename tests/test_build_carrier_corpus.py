import unittest

from lmcodec.lm import default_vocab
from scripts.build_carrier_corpus import SEED_LINES, build_lines


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


if __name__ == "__main__":
    unittest.main()
