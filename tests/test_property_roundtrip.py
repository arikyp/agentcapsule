import random
import unittest

from lmcodec.codec import CodecSettings, decode, encode
from lmcodec.errors import LMCodecError
from lmcodec.lm import FixedLM
from lmcodec.probability import ProbabilityShapeSettings


PAYLOAD_SIZES = (0, 1, 2, 3, 7, 16, 31, 64, 255, 256, 1024, 4096)
SEED = 20260505


class PropertyRoundtripTests(unittest.TestCase):
    def test_fixed_seed_random_payloads_roundtrip_losslessly(self) -> None:
        rng = random.Random(SEED)

        for size in PAYLOAD_SIZES:
            with self.subTest(size=size):
                payload = _random_payload(rng, size)
                self.assertEqual(decode(encode(payload)), payload)

    def test_same_payload_model_and_settings_produce_identical_message_text(self) -> None:
        payload = bytes((idx * 131 + 17) % 256 for idx in range(257))
        model = FixedLM()
        settings = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.25, temperature=1.5))

        messages = [encode(payload, model=model, settings=settings, wrap=80) for _ in range(6)]

        self.assertEqual(messages, [messages[0]] * len(messages))

    def test_single_carrier_character_mutation_is_detected(self) -> None:
        rng = random.Random(SEED + 1)

        for size in (0, 1, 16, 255, 1024):
            with self.subTest(size=size):
                payload = _random_payload(rng, size)
                message = encode(payload, wrap=80)
                corrupted = _mutate_one_carrier_character(message)

                with self.assertRaises(LMCodecError):
                    decode(corrupted)


def _random_payload(rng: random.Random, size: int) -> bytes:
    return bytes(rng.randrange(256) for _ in range(size))


def _mutate_one_carrier_character(message: str) -> str:
    lines = message.split("\n")
    payload_start = lines.index("") + 1
    payload_end = lines.index("-----END LMCODEC-----")
    carrier = "".join(lines[payload_start:payload_end])
    if not carrier:
        raise AssertionError("encoded carrier text unexpectedly empty")

    vocab = FixedLM().vocab
    index = len(carrier) // 3
    original = carrier[index]
    replacement = vocab[(vocab.index(original) + 1) % len(vocab)]
    mutated = carrier[:index] + replacement + carrier[index + 1 :]
    return "\n".join(lines[:payload_start] + [mutated] + lines[payload_end:])


if __name__ == "__main__":
    unittest.main()
