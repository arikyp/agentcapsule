import tempfile
import unittest
from pathlib import Path

from scripts.split_corpus import _segments, main, split_report


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

    def test_split_report_records_filtering_and_coverage(self) -> None:
        original = "alpha beta\nbad!\n"
        filtered = "alpha beta\nbad\n"
        report = split_report(
            original,
            filtered,
            ["alpha beta"],
            ["bad"],
            filter_vocab=True,
            heldout_ratio=0.25,
            seed=123,
        )

        self.assertEqual(report["filter_vocab"], True)
        self.assertEqual(report["original_invalid_chars"], ["!"])
        self.assertEqual(report["filtered_invalid_chars"], [])
        self.assertEqual(report["segments"], 2)
        self.assertGreater(report["shared_unique_chars"], 0)


if __name__ == "__main__":
    unittest.main()
