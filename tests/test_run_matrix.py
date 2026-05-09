import tempfile
import unittest
import json
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
                    {"name": "text_repeat", "kind": "text_repeat", "bytes": 5, "token": "ab"},
                ],
                output,
            )

            self.assertEqual([item["bytes"] for item in payloads], [0, 3, 4, 5])
            self.assertEqual((output / "empty.bin").read_bytes(), b"")
            self.assertEqual((output / "text.bin").read_bytes(), b"abc")
            self.assertEqual((output / "range.bin").read_bytes(), bytes([254, 255, 0, 1]))
            self.assertEqual((output / "text_repeat.bin").read_bytes(), b"ababa")

    def test_file_corpus_materializes_filtered_realish_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            source = root / "source.md"
            corpus = root / "corpus.txt"
            report = root / "report.json"
            source.write_text("Hello, LMCodec!\nSymbols: []{}_\n", encoding="utf-8")

            run_matrix._write_file_corpus(
                {"name": "realish", "kind": "files", "paths": [str(source)]},
                corpus,
                report,
            )

            text = corpus.read_text(encoding="utf-8")
            self.assertIn("hello", text)
            self.assertIn("lmcodec", text)
            self.assertNotIn("[", text)
            self.assertTrue(report.exists())

    def test_candidate_rankings_use_hard_gates_before_quality(self) -> None:
        records = [
            {
                "candidate": "better_quality_failed",
                "hard_gate_passed": False,
                "heldout_nll_bits": 1.0,
                "avg_entropy_bits": 5.0,
                "bits_per_carrier_char": 5.9,
                "encode_seconds": 2.0,
                "decode_seconds": 1.0,
                "avg_top_probability": 0.2,
            },
            {
                "candidate": "passed",
                "hard_gate_passed": True,
                "heldout_nll_bits": 3.0,
                "avg_entropy_bits": 5.7,
                "bits_per_carrier_char": 5.9,
                "encode_seconds": 1.0,
                "decode_seconds": 0.5,
                "avg_top_probability": 0.1,
            },
        ]

        rankings = run_matrix._candidate_rankings(records)

        self.assertEqual(rankings[0]["candidate"], "passed")
        self.assertEqual(rankings[1]["candidate"], "better_quality_failed")
        self.assertEqual(rankings[0]["mean_encode_seconds"], 1.0)

    def test_matrix_hard_gate_allows_external_golden_verification(self) -> None:
        result = {
            "error_message": None,
            "roundtrip_success": True,
            "model_fingerprint_stable": True,
            "convergence_failure_count": 0,
            "promotion": {
                "passed": False,
                "checks": {
                    "decoded_sha256_matches": True,
                    "entropy_above_minimum": True,
                    "golden_tests_unaffected": "not_checked_by_runner",
                },
            },
        }

        hard_gate = run_matrix._hard_gate(result)

        self.assertTrue(hard_gate["passed"])

    def test_load_progress_records_keeps_latest_record_by_experiment(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "progress.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"experiment_name": "cell", "status": "completed"}),
                        json.dumps({"experiment_name": "cell", "status": "timeout"}),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            records = run_matrix._load_progress_records(path)

            self.assertEqual(records["cell"]["status"], "timeout")

    def test_reusable_models_are_planned_for_dry_run_configs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            corpus = {"name": "corpus", "train_path": str(root / "train.txt"), "heldout_path": str(root / "heldout.txt")}
            candidate = {
                "name": "ngram_cached",
                "reuse_model_per_corpus": True,
                "model": {"type": "ngram", "training": {"order": 1}},
            }

            reusable = run_matrix._prepare_reusable_models([candidate], [corpus], root / "models", materialize=False)
            configs = run_matrix._write_configs(
                {"matrix_name": "test", "candidates": [candidate]},
                [{"name": "payload", "path": str(root / "payload.bin")}],
                [corpus],
                root,
                reusable,
            )

            config = json.loads(Path(configs[0]["config_path"]).read_text(encoding="utf-8"))
            self.assertEqual(config["model"]["type"], "ngram")
            self.assertIn("models/ngram_cached-corpus.json", config["model"]["path"])
            self.assertNotIn("training", config["model"])
            self.assertFalse(Path(config["model"]["path"]).exists())

    def test_reusable_models_materialize_once_per_candidate_corpus(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            train = root / "train.txt"
            train.write_text("abcabcabc\n", encoding="utf-8")
            corpus = {"name": "corpus", "train_path": str(train), "heldout_path": str(root / "heldout.txt")}
            candidate = {
                "name": "ngram_cached",
                "reuse_model_per_corpus": True,
                "model": {"type": "ngram", "training": {"order": 1, "alpha": 1.0, "uniform_mix": 0.75}},
            }

            reusable = run_matrix._prepare_reusable_models([candidate], [corpus], root / "models", materialize=True)
            model_path = Path(reusable["ngram_cached"]["corpus"]["path"])

            self.assertTrue(model_path.exists())
            self.assertEqual(json.loads(model_path.read_text(encoding="utf-8"))["model_type"], "ngram-v1")


if __name__ == "__main__":
    unittest.main()
