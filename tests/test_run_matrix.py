import tempfile
import unittest
from pathlib import Path

from scripts import run_matrix


class RunMatrixTests(unittest.TestCase):
    def test_payload_suite_materializes_deterministic_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir)
            payloads = run_matrix._materialize_payloads(
                [
                    {"name": "empty", "kind": "empty"},
                    {"name": "text", "kind": "text", "text": "abc"},
                    {"name": "range", "kind": "range", "start": 254, "count": 4},
                ],
                output,
            )

            self.assertEqual([item["bytes"] for item in payloads], [0, 3, 4])
            self.assertEqual((output / "empty.bin").read_bytes(), b"")
            self.assertEqual((output / "text.bin").read_bytes(), b"abc")
            self.assertEqual((output / "range.bin").read_bytes(), bytes([254, 255, 0, 1]))

    def test_candidate_rankings_use_hard_gates_before_quality(self) -> None:
        records = [
            {
                "candidate": "better_quality_failed",
                "hard_gate_passed": False,
                "heldout_nll_bits": 1.0,
                "avg_entropy_bits": 5.0,
                "bits_per_carrier_char": 5.9,
                "avg_top_probability": 0.2,
            },
            {
                "candidate": "passed",
                "hard_gate_passed": True,
                "heldout_nll_bits": 3.0,
                "avg_entropy_bits": 5.7,
                "bits_per_carrier_char": 5.9,
                "avg_top_probability": 0.1,
            },
        ]

        rankings = run_matrix._candidate_rankings(records)

        self.assertEqual(rankings[0]["candidate"], "passed")
        self.assertEqual(rankings[1]["candidate"], "better_quality_failed")


if __name__ == "__main__":
    unittest.main()
