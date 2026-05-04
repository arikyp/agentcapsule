import hashlib
import unittest
from pathlib import Path

from lmcodec.codec import CodecSettings, decode, encode
from lmcodec.lm import FixedLM, NGramLM
from lmcodec.probability import ProbabilityShapeSettings
from lmcodec.transformer import TransformerLM

ROOT = Path(__file__).resolve().parents[1]
FIXED_GOLDEN_MESSAGE = ROOT / "tests" / "fixtures" / "golden_message_v1.txt"
NGRAM_MODEL = ROOT / "tests" / "fixtures" / "ngram_model_v1.json"
NGRAM_GOLDEN_MESSAGE = ROOT / "tests" / "fixtures" / "ngram_golden_message_v1.txt"
TRANSFORMER_MODEL = ROOT / "tests" / "fixtures" / "transformer_model_v1.json"
TRANSFORMER_GOLDEN_MESSAGE = ROOT / "tests" / "fixtures" / "transformer_golden_message_v1.txt"
PAYLOAD = bytes(range(256))
TRANSFORMER_SETTINGS = CodecSettings(shape=ProbabilityShapeSettings(uniform_mix=0.80, temperature=1.25))

EXPECTED_MODEL_FINGERPRINT = "d60583f4d741e42cb713b11c78b8ffc89cda1ee05eca522929bec8cbdb423be8"
EXPECTED_MESSAGE_SHA256 = "f53ec3604a378788b20cf6e0aadbfe441a063aa7ce1cea0bef9b1427cbd21e35"
EXPECTED_NGRAM_MODEL_FINGERPRINT = "b1cd62a9019b67e0a42913dac1dca09852b4931f09afa87bb8e62089fe184a3a"
EXPECTED_NGRAM_MESSAGE_SHA256 = "53c062a238764c72caa9dd338d37682ab350d7ace4251e9778ba13ae97d99512"
EXPECTED_TRANSFORMER_MODEL_FINGERPRINT = "cfc75d7b54524f7a09a90454d89768aa4eb75b17546607c376760e2fc9d8f851"
EXPECTED_TRANSFORMER_MESSAGE_SHA256 = "7713a0b7208462485f854ab58e5423f16c16360aeff524f1597ba49c840ad96b"
EXPECTED_PAYLOAD_SHA256 = "40aff2e9d2d8922e47afd4648e6967497158785fbd1da870e7110266bf944880"


class GoldenTests(unittest.TestCase):
    def test_golden_v1(self) -> None:
        model = FixedLM()
        message = _read_canonical(FIXED_GOLDEN_MESSAGE)

        self.assertEqual(model.fingerprint, EXPECTED_MODEL_FINGERPRINT)
        self.assertEqual(_sha256_text(message), EXPECTED_MESSAGE_SHA256)
        self.assertEqual(hashlib.sha256(PAYLOAD).hexdigest(), EXPECTED_PAYLOAD_SHA256)
        self.assertEqual(decode(message, model=model), PAYLOAD)
        self.assertEqual(encode(PAYLOAD, model=model, wrap=80), message)
        self.assertEqual(encode(PAYLOAD, model=model, wrap=80), encode(PAYLOAD, model=model, wrap=80))

    def test_ngram_golden_v1(self) -> None:
        model = NGramLM.load(NGRAM_MODEL)
        message = _read_canonical(NGRAM_GOLDEN_MESSAGE)

        self.assertEqual(model.fingerprint, EXPECTED_NGRAM_MODEL_FINGERPRINT)
        self.assertEqual(_sha256_text(message), EXPECTED_NGRAM_MESSAGE_SHA256)
        self.assertEqual(hashlib.sha256(PAYLOAD).hexdigest(), EXPECTED_PAYLOAD_SHA256)
        self.assertEqual(decode(message, model=model), PAYLOAD)
        self.assertEqual(encode(PAYLOAD, model=model, wrap=80), message)
        self.assertEqual(encode(PAYLOAD, model=model, wrap=80), encode(PAYLOAD, model=model, wrap=80))

    def test_transformer_golden_v1(self) -> None:
        model = TransformerLM.load(TRANSFORMER_MODEL)
        message = _read_canonical(TRANSFORMER_GOLDEN_MESSAGE)

        self.assertEqual(model.fingerprint, EXPECTED_TRANSFORMER_MODEL_FINGERPRINT)
        self.assertEqual(_sha256_text(message), EXPECTED_TRANSFORMER_MESSAGE_SHA256)
        self.assertEqual(hashlib.sha256(PAYLOAD).hexdigest(), EXPECTED_PAYLOAD_SHA256)
        self.assertEqual(decode(message, model=model), PAYLOAD)
        self.assertEqual(
            encode(PAYLOAD, model=model, settings=TRANSFORMER_SETTINGS, wrap=80, max_steps=100000),
            message,
        )
        self.assertEqual(
            encode(PAYLOAD, model=model, settings=TRANSFORMER_SETTINGS, wrap=80, max_steps=100000),
            encode(PAYLOAD, model=model, settings=TRANSFORMER_SETTINGS, wrap=80, max_steps=100000),
        )


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _read_canonical(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")


if __name__ == "__main__":
    unittest.main()
