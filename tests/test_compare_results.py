import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from scripts import compare_results


class CompareResultsTests(unittest.TestCase):
    def test_compare_results_prints_markdown_sorted_by_nll(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            first = root / "first.json"
            second = root / "second.json"
            _write_result(first, "first", heldout_nll_bits=4.0)
            _write_result(second, "second", heldout_nll_bits=3.0)

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                code = compare_results.main([str(first), str(second)])

            self.assertEqual(code, 0)
            lines = stdout.getvalue().splitlines()
            self.assertIn("experiment_name", lines[0])
            self.assertIn("second", lines[2])
            self.assertIn("first", lines[3])

    def test_compare_results_writes_json_with_deltas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            baseline = root / "baseline.json"
            candidate = root / "candidate.json"
            output = root / "comparison.json"
            _write_result(baseline, "baseline", heldout_nll_bits=4.0, avg_entropy_bits=5.5)
            _write_result(candidate, "candidate", heldout_nll_bits=3.5, avg_entropy_bits=5.7)

            with contextlib.redirect_stdout(io.StringIO()):
                code = compare_results.main(
                    [
                        str(candidate),
                        "--baseline",
                        str(baseline),
                        "--json-out",
                        str(output),
                    ]
                )

            self.assertEqual(code, 0)
            records = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(records[0]["experiment_name"], "candidate")
            self.assertAlmostEqual(records[0]["delta_heldout_nll_bits"], -0.5)
            self.assertAlmostEqual(records[0]["delta_avg_entropy_bits"], 0.2)


def _write_result(
    path: Path,
    name: str,
    *,
    heldout_nll_bits: float,
    avg_entropy_bits: float = 5.8,
) -> None:
    path.write_text(
        json.dumps(
            {
                "experiment_name": name,
                "config_path": f"experiments/configs/{name}.json",
                "payload_bytes": 128,
                "roundtrip_success": True,
                "promotion": {"passed": True},
                "avg_entropy_bits": avg_entropy_bits,
                "heldout_nll_bits": heldout_nll_bits,
                "bits_per_carrier_char": 5.9,
                "carrier_chars": 180,
                "carrier_diversity": {
                    "unique_character_count": 64,
                    "longest_repeated_run": 2,
                },
                "avg_top_probability": 0.1,
                "error_message": None,
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
