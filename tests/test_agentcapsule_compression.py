import os
import unittest
from unittest.mock import patch

from agentcapsule.compression import COMPRESSION_ZSTD, compress_payload, decompress_payload
from agentcapsule.errors import CapsuleVerificationError


class AgentCapsuleCompressionTests(unittest.TestCase):
    def setUp(self) -> None:
        try:
            import zstandard  # noqa: F401
        except ImportError:
            self.skipTest("zstandard not installed")

    def test_zstd_roundtrip_with_default_limit(self) -> None:
        payload = (b"abc123\n" * 1000)
        compressed, mode = compress_payload(payload, mode=COMPRESSION_ZSTD)
        self.assertEqual(mode, COMPRESSION_ZSTD)
        self.assertEqual(decompress_payload(compressed, mode=COMPRESSION_ZSTD), payload)

    def test_zstd_decompress_fails_when_limit_too_small(self) -> None:
        payload = (b"abc123\n" * 1000)
        compressed, _ = compress_payload(payload, mode=COMPRESSION_ZSTD)
        with patch.dict(os.environ, {"AGENTCAPSULE_ZSTD_MAX_OUTPUT_SIZE": "16"}, clear=False):
            with self.assertRaisesRegex(CapsuleVerificationError, "exceeded max output size"):
                decompress_payload(compressed, mode=COMPRESSION_ZSTD)


if __name__ == "__main__":
    unittest.main()
