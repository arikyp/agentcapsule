import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "schemas" / "benchmark_result_v1.json"


class BenchmarkSchemaTests(unittest.TestCase):
    def test_benchmark_schema_is_valid_json_and_documents_required_fields(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertIn("results", schema["required"])
        self.assertIn("payload", schema["required"])

        result_required = set(schema["$defs"]["result"]["required"])
        self.assertTrue(
            {
                "payload_sha256",
                "model_fingerprint",
                "carrier_chars",
                "bits_per_carrier_char",
                "encode_seconds",
                "decode_seconds",
                "roundtrip_success",
                "carrier_quality",
                "error_message",
            }.issubset(result_required)
        )

    def test_benchmark_schema_allows_sweep_extra_result_fields(self) -> None:
        result_properties = schema_result_properties()

        self.assertIn("score", result_properties)
        self.assertIn("carrier_diversity", result_properties)


def schema_result_properties() -> dict[str, object]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return schema["$defs"]["result"]["properties"]


if __name__ == "__main__":
    unittest.main()
