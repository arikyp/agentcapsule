import tempfile
import unittest
from pathlib import Path

from scripts.split_corpus import _segments, main


class SplitCorpusTests(unittest.TestCase):
    def test_segments_coalesces_short_lines(self) -> None:
        segments = _segments("one\ntwo three\n\nfour five six\n", min_chars=8)

        self.assertEqual(segments, ["one two three", "four five six"])

    def test_script_writes_deterministic_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.txt"
            train = root / "train.txt"
            heldout = root / "heldout.txt"
            source.write_text(
                "alpha beta gamma\n"
                "delta epsilon zeta\n"
                "eta theta iota\n"
                "kappa lambda mu\n",
                encoding="utf-8",
            )

            code = main(
                [
                    "--input",
                    str(source),
                    "--train-out",
                    str(train),
                    "--heldout-out",
                    str(heldout),
                    "--heldout-ratio",
                    "0.25",
                    "--seed",
                    "123",
                    "--min-segment-chars",
                    "8",
                ]
            )

            self.assertEqual(code, 0)
            self.assertTrue(train.read_text(encoding="utf-8"))
            self.assertTrue(heldout.read_text(encoding="utf-8"))
            self.assertNotEqual(train.read_text(encoding="utf-8"), heldout.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
