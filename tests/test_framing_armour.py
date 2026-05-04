import unittest

from lmcodec.armour import make_armour, parse_armour
from lmcodec.errors import LMCodecError
from lmcodec.framing import build_frame, parse_frame


class FramingArmourTests(unittest.TestCase):
    def test_frame_roundtrip_empty_payload(self) -> None:
        self.assertEqual(parse_frame(build_frame(b"")), b"")

    def test_frame_roundtrip_payload(self) -> None:
        payload = bytes(range(32))
        self.assertEqual(parse_frame(build_frame(payload)), payload)

    def test_crc_failure(self) -> None:
        frame = bytearray(build_frame(b"payload"))
        frame[-1] ^= 0x01

        with self.assertRaisesRegex(LMCodecError, "CRC mismatch"):
            parse_frame(bytes(frame))

    def test_armour_roundtrip_and_crlf_normalization(self) -> None:
        text = make_armour(
            "abc123",
            model_fingerprint="f" * 64,
            settings={"TOT": "65536", "TOPK": "0"},
            wrap=3,
        )
        crlf_text = text.replace("\n", "\r\n")
        block = parse_armour("noise\n" + crlf_text + "\nnoise")

        self.assertEqual(block.version, 1)
        self.assertEqual(block.model_fingerprint, "f" * 64)
        self.assertEqual(block.settings, {"TOT": "65536", "TOPK": "0"})
        self.assertEqual(block.payload_text, "abc123")


if __name__ == "__main__":
    unittest.main()

