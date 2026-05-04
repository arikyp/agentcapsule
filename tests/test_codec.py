import unittest

from lmcodec.codec import CodecSettings, decode, encode
from lmcodec.errors import LMCodecError
from lmcodec.lm import FixedLM
from lmcodec.probability import ProbabilityShapeSettings


class CodecTests(unittest.TestCase):
    def test_roundtrip_payload_sizes(self) -> None:
        payloads = [
            b"",
            b"x",
            b"0123456789abcdef",
            bytes(range(256)),
            bytes((idx * 37) % 256 for idx in range(1024)),
        ]

        for payload in payloads:
            with self.subTest(size=len(payload)):
                message = encode(payload, wrap=80)
                self.assertEqual(decode(message), payload)

    def test_same_run_determinism(self) -> None:
        payload = bytes(range(64))

        self.assertEqual(encode(payload), encode(payload))

    def test_fingerprint_mismatch_fails_fast(self) -> None:
        message = encode(b"payload")
        altered = message.replace("model_fingerprint: ", "model_fingerprint: 0", 1)

        with self.assertRaisesRegex(LMCodecError, "fingerprint mismatch"):
            decode(altered)

    def test_corruption_fails(self) -> None:
        message = encode(b"payload that should detect corruption", wrap=0)
        lines = message.split("\n")
        payload_idx = lines.index("") + 1
        chars = list(lines[payload_idx])
        chars[len(chars) // 2] = "A" if chars[len(chars) // 2] != "A" else "B"
        lines[payload_idx] = "".join(chars)
        corrupted = "\n".join(lines)

        with self.assertRaises(LMCodecError):
            decode(corrupted)

    def test_invalid_carrier_token_fails(self) -> None:
        model = FixedLM(vocab="abc ")
        message = encode(b"payload", model=model)
        lines = message.split("\n")
        payload_idx = lines.index("") + 1
        lines[payload_idx] = "~" + lines[payload_idx]

        with self.assertRaisesRegex(LMCodecError, "invalid carrier token"):
            decode("\n".join(lines), model=model)

    def test_shaped_settings_roundtrip_from_armour(self) -> None:
        settings = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.25, temperature=1.5))
        message = encode(b"shaped payload", settings=settings)

        self.assertIn("SHAPE_UNIFORM_MIX=0.25", message)
        self.assertEqual(decode(message), b"shaped payload")

    def test_explicit_decode_settings_must_match_armour(self) -> None:
        settings = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.25))
        message = encode(b"shaped payload", settings=settings)

        with self.assertRaisesRegex(LMCodecError, "invalid settings"):
            decode(message, settings=CodecSettings())


if __name__ == "__main__":
    unittest.main()
